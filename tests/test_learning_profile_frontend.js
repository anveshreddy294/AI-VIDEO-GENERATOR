const test=require('node:test');const assert=require('node:assert/strict');
const ui=require('../app/static/learning-profile.js');
test('interest selection is required and custom entries are bounded',()=>{
    const base={education_level:'Secondary',interested_domains:['Sports'],custom_interest:''};
    assert.equal(ui.validate(base),'');assert.match(ui.validate({...base,interested_domains:[]}),/at least one/);
    assert.match(ui.validate({...base,interested_domains:['Other']}),/custom/);
    assert.match(ui.validate({...base,custom_interest:'<script>'}),/without markup/);
});
test('profile API uses protected same-origin request and rejects malformed completion',async()=>{
    const calls=[];const auth={protectedFetch:async(path,options)=>{calls.push({path,options});return {ok:true,json:async()=>({user_id:'owned-user',complete:true})};}};
    assert.equal((await ui.request(auth)).complete,true);
    assert.equal(calls[0].path,'/api/learning-profile');
    await assert.rejects(ui.request({protectedFetch:async()=>({ok:false,status:422})}),/select at least one/);
});
