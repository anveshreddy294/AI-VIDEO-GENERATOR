"""Private PostgreSQL domain transport for new records; older records stay in Supabase.

This is not an HTTP endpoint or a general SQL/PostgREST proxy. Only the existing
source, knowledge and session repository operations below are accepted. Auth is
always delegated to Supabase; a missing/unavailable local database never becomes
a write fallback to Supabase.
"""
from __future__ import annotations

import re
from ...core import postgres
from ...core.config import settings
from ...core.supabase import SupabaseAuthenticationError, SupabaseConflict, SupabaseResponseError, SupabaseUnavailable

TABLES = frozenset({'sources','source_versions','content_units','topics','subtopics','concepts',
                   'concept_relationships','content_concepts','learning_sessions'})
RPCS = {
    'visualai_commit_source_ingestion': {'p_source':'jsonb','p_version':'jsonb','p_units':'jsonb'},
    'visualai_source_index_status': {'p_source_id':'text','p_version':'integer','p_status':'text','p_error':'text'},
    'visualai_commit_knowledge_snapshot': {'p_source_id':'text','p_source_version':'integer','p_operation_id':'uuid','p_payload':'jsonb'},
    'visualai_rebuild_verified_knowledge': {'p_source_id':'text','p_source_version':'integer','p_expected_hash':'text','p_operation_id':'uuid','p_payload':'jsonb'},
    'visualai_mutate_learning_session': {'p_action':'text','p_session_id':'uuid','p_source_id':'text','p_source_version':'integer','p_topic_id':'text','p_subtopic_id':'text','p_concept_ids':'text[]'},
    'visualai_assessment_transaction': {'p_action':'text','p_user_id':'uuid','p_assessment_id':'text','p_payload':'jsonb'},
    'visualai_learning_transaction': {'p_action':'text','p_user_id':'uuid','p_learning_session_id':'uuid','p_payload':'jsonb'},
    'visualai_remediation_video': {'p_action':'text','p_user_id':'uuid','p_learning_session_id':'uuid','p_remediation_id':'text','p_payload':'jsonb'},
}
IDENTIFIER = re.compile(r'^[a-z][a-z0-9_]*$')
MAX_ROWS = 10000


def enabled():
    return settings.source_persistence_provider == 'postgres'


def wrap(runtime, user, token):
    if not enabled() or isinstance(runtime, LearningStorage):
        return runtime
    return LearningStorage(runtime, user, token)


class LearningStorage:
    def __init__(self, auth, user, token):
        verified = auth.verify_user(token)
        if verified.user_id != user.user_id:
            raise SupabaseAuthenticationError('Storage ownership mismatch')
        self.auth, self.user, self._token = auth, verified, token

    def verify_user(self, token):
        verified = self.auth.verify_user(token)
        if verified.user_id != self.user.user_id:
            raise SupabaseAuthenticationError('Storage ownership mismatch')
        return verified

    def _owner(self, connection):
        connection.execute("SELECT set_config('visualai.owner_id',%s,true)", (str(self.user.user_id),))

    def _exists(self, table, column, value):
        from psycopg import sql
        with postgres.transaction() as connection:
            self._owner(connection)
            return connection.execute(sql.SQL('SELECT 1 FROM visualai_learning.{} WHERE user_id=%s AND {}=%s LIMIT 1')
                .format(sql.Identifier(table),sql.Identifier(column)), (self.user.user_id,value)).fetchone() is not None

    def _local_rpc(self, name, body):
        if name == 'visualai_commit_source_ingestion':
            return True
        if name == 'visualai_mutate_learning_session':
            if body.get('p_source_id'):
                return self._exists('sources','source_id',body['p_source_id'])
            return self._exists('learning_sessions','session_id',body.get('p_session_id'))
        if name == 'visualai_assessment_transaction':
            payload = body.get('p_payload') or {}
            if body.get('p_action') == 'create':
                return self._exists('learning_sessions','session_id',payload.get('learning_session_id'))
            return self._exists('assessment_sessions','session_id',body.get('p_assessment_id'))
        if name in {'visualai_learning_transaction','visualai_remediation_video'}:
            return self._exists('learning_sessions','session_id',body.get('p_learning_session_id'))
        return self._exists('sources','source_id',body.get('p_source_id'))

    def _rpc(self, name, body):
        from psycopg import sql
        from psycopg.types.json import Jsonb
        from psycopg.errors import UniqueViolation, ObjectNotInPrerequisiteState
        from psycopg.errors import RaiseException, InsufficientPrivilege
        from psycopg import DataError, IntegrityError
        if set(body)-RPCS[name].keys():
            raise SupabaseResponseError('Unsupported storage contract')
        if 'p_user_id' in body and str(body['p_user_id']) != str(self.user.user_id):
            raise SupabaseAuthenticationError('Storage ownership mismatch')
        arguments, values = [], []
        for key, value in body.items():
            kind = RPCS[name][key]
            arguments.append(sql.SQL('{} => %s::{}').format(sql.Identifier(key),sql.SQL(kind)))
            values.append(Jsonb(value) if kind=='jsonb' else value)
        try:
            with postgres.transaction() as connection:
                self._owner(connection)
                connection.execute('INSERT INTO visualai_learning.profiles(id) VALUES (%s) ON CONFLICT(id) DO NOTHING', (self.user.user_id,))
                return connection.execute(sql.SQL('SELECT visualai_learning.{}({})').format(
                    sql.Identifier(name),sql.SQL(',').join(arguments)), values).fetchone()[0]
        except postgres.VideoDatabaseError as error:
            if isinstance(error.__context__, (UniqueViolation,ObjectNotInPrerequisiteState)):
                raise SupabaseConflict('Learning storage conflict') from None
            if isinstance(error.__context__, (RaiseException,InsufficientPrivilege,DataError,IntegrityError)):
                raise SupabaseResponseError('Learning storage rejected the operation') from None
            raise SupabaseUnavailable('Learning storage unavailable') from None

    @staticmethod
    def _number(value, default, maximum):
        try:
            number = int(value) if value is not None else default
        except (ValueError,TypeError):
            raise SupabaseResponseError('Invalid storage pagination') from None
        if not 0 <= number <= maximum:
            raise SupabaseResponseError('Invalid storage pagination')
        return number

    @staticmethod
    def _projection(row, select):
        if select == '*':
            return row
        nested = 'content:content_units('
        if nested in select:
            base, inner = select.split(nested,1)
            result = LearningStorage._projection(row,base.rstrip(','))
            result['content'] = LearningStorage._projection(row['content'],inner.rstrip(')'))
            return result
        result = {}
        for field in select.split(','):
            pair = field.split(':')
            if not 1 <= len(pair) <= 2 or any(not IDENTIFIER.fullmatch(x) for x in pair):
                raise SupabaseResponseError('Unsupported storage projection')
            result[pair[0]] = row.get(pair[-1])
        return result

    def _read(self, table, params):
        from psycopg import sql
        limit = self._number(params.get('limit'),500,MAX_ROWS)
        offset = self._number(params.get('offset'),0,MAX_ROWS)
        with postgres.transaction() as connection:
            self._owner(connection)
            columns = {row[0] for row in connection.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='visualai_learning' AND table_name=%s", (table,)).fetchall()}
            clauses = [sql.SQL('t.user_id=%s')]
            values = [self.user.user_id]
            for key, value in params.items():
                if key in {'select','order','limit','offset'}:
                    continue
                if key not in columns:
                    raise SupabaseResponseError('Unsupported storage filter')
                if value.startswith('eq.'):
                    clauses.append(sql.SQL('t.{}=%s').format(sql.Identifier(key)))
                    values.append(value[3:])
                elif value.startswith('in.(') and value.endswith(')'):
                    entries = value[4:-1].split(',')
                    clauses.append(sql.SQL('t.{} IN ({})').format(sql.Identifier(key),sql.SQL(',').join(sql.Placeholder() for _ in entries)))
                    values.extend(entries)
                else:
                    raise SupabaseResponseError('Unsupported storage filter')
            orders = []
            for order in params.get('order','source_id').split(','):
                parts = order.split('.')
                if parts[0] not in columns or len(parts)>2 or len(parts)==2 and parts[1] not in {'asc','desc'}:
                    raise SupabaseResponseError('Unsupported storage order')
                orders.append(sql.SQL('t.{} {}').format(sql.Identifier(parts[0]),sql.SQL('DESC' if parts[-1]=='desc' else 'ASC')))
            projection = sql.SQL('to_jsonb(t)')
            join = sql.SQL('')
            if table == 'content_concepts' and 'content:content_units(' in params.get('select',''):
                projection = sql.SQL("to_jsonb(t)||jsonb_build_object('content',to_jsonb(u))")
                join = sql.SQL(' JOIN visualai_learning.content_units u ON (u.user_id,u.source_id,u.source_version,u.content_id)=(t.user_id,t.source_id,t.source_version,t.content_id) ')
            query = sql.SQL('SELECT {} FROM visualai_learning.{} t {} WHERE {} ORDER BY {} LIMIT %s OFFSET %s').format(
                projection,sql.Identifier(table),join,sql.SQL(' AND ').join(clauses),sql.SQL(',').join(orders))
            rows = connection.execute(query,values+[limit,offset]).fetchall()
        return [self._projection(row[0],params.get('select','*')) for row in rows]

    def _read_request(self, table, params):
        source = params.get('source_id','')
        sid = params.get('session_id','')
        if source.startswith('eq.'):
            if self._exists('sources','source_id',source[3:]):
                return self._read(table,params)
            return self.auth.user_request('GET','/rest/v1/'+table,token=self._token,params=params)
        if table == 'learning_sessions' and sid.startswith('eq.'):
            if self._exists('learning_sessions','session_id',sid[3:]):
                return self._read(table,params)
            return self.auth.user_request('GET','/rest/v1/'+table,token=self._token,params=params)
        if table not in {'sources','learning_sessions'}:
            raise SupabaseResponseError('Exact source scope required')
        # Merge bounded historical/new lists BEFORE paging; otherwise page boundaries
        # can hide records or repeat them. Fail explicitly on an incomplete list.
        merged = []
        for local in (True,False):
            rows = []
            for offset in range(0,MAX_ROWS,500):
                page_params = params | {'select':'*','limit':'500','offset':str(offset)}
                page = self._read(table,page_params) if local else self.auth.user_request('GET','/rest/v1/'+table,token=self._token,params=page_params)
                if not isinstance(page,list):
                    raise SupabaseResponseError('Invalid storage response')
                rows.extend(page)
                if len(page)<500:
                    break
            else:
                raise SupabaseResponseError('Storage listing too large')
            merged.extend(rows)
        identity = 'source_id' if table=='sources' else 'session_id'
        if len({row[identity] for row in merged})!=len(merged):
            raise SupabaseConflict('Ambiguous storage identity')
        for order in reversed(params.get('order',identity).split(',')):
            parts = order.split('.')
            merged.sort(key=lambda r:(r.get(parts[0]) is None,r.get(parts[0])),reverse=parts[-1]=='desc')
        offset = self._number(params.get('offset'),0,MAX_ROWS)
        limit = self._number(params.get('limit'),500,MAX_ROWS)
        return [self._projection(row,params.get('select','*')) for row in merged[offset:offset+limit]]

    def user_request(self, method, path, *, token, params=None, body=None, **kwargs):
        if token != self._token:
            raise SupabaseAuthenticationError('Storage ownership mismatch')
        try:
            if method=='GET' and path.removeprefix('/rest/v1/') in TABLES:
                return self._read_request(path.removeprefix('/rest/v1/'),dict(params or {}))
            name = path.removeprefix('/rest/v1/rpc/')
            if method=='POST' and name in RPCS:
                return self._rpc(name,body or {}) if self._local_rpc(name,body or {}) else self.auth.user_request(method,path,token=token,body=body,params=params,**kwargs)
            return self.auth.user_request(method,path,token=token,params=params,body=body,**kwargs)
        except postgres.VideoDatabaseError:
            raise SupabaseUnavailable('Learning storage unavailable') from None

    def admin_request(self, method, path, *, body=None, **kwargs):
        name = path.removeprefix('/rest/v1/rpc/')
        if method != 'POST' or name not in {'visualai_assessment_transaction','visualai_learning_transaction','visualai_remediation_video'}:
            raise SupabaseResponseError('Unsupported backend storage operation')
        body = body or {}
        if str(body.get('p_user_id')) != str(self.user.user_id):
            raise SupabaseAuthenticationError('Storage ownership mismatch')
        try:
            return self._rpc(name,body) if self._local_rpc(name,body) else self.auth.admin_request(method,path,body=body,**kwargs)
        except postgres.VideoDatabaseError:
            raise SupabaseUnavailable('Learning storage unavailable') from None
