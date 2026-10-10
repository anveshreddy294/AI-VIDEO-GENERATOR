/* Account preferences use the existing bearer helper; no identity or secrets in form data. */
(() => {
    'use strict';
    const domains=['Sports','Dance','Music','Gaming','Technology','Science','Nature and Animals','Art and Design','Movies and Animation','Business and Entrepreneurship','Fitness','Other'];
    const icons=['⚽','💃','🎵','🎮','💻','🔬','🌿','🎨','🎬','💼','🏃','✦'];
    function validate(value) {
        if(!['Primary','Secondary','Undergraduate','Other'].includes(value.education_level)) return 'Choose your education level.';
        if(!Array.isArray(value.interested_domains) || !value.interested_domains.length || value.interested_domains.some(v=>!domains.includes(v)) || new Set(value.interested_domains).size!==value.interested_domains.length) return 'Choose at least one interested domain.';
        if(value.interested_domains.includes('Other') && !value.custom_interest.trim()) return 'Enter your custom interest.';
        if(value.custom_interest.length>80 || (value.custom_interest && !/^[\p{L}\p{N}_ .,'&()+/-]+$/u.test(value.custom_interest))) return 'Use a short interest name without markup.';
        return '';
    }
    async function request(auth,method='GET',body) {
        const response=await auth.protectedFetch('/api/learning-profile',{method,...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
        if(!response.ok) throw Error(response.status===422?'Check your profile details and select at least one interest.':'Your learning profile could not be saved or loaded. Please try again.');
        const value=await response.json();
        if(!value || typeof value.complete!=='boolean' || typeof value.user_id!=='string') throw Error('Invalid learning profile response.');
        return value;
    }
    async function ensure(auth) {
        const profile=await request(auth);
        if(!profile.complete){window.location.assign('/profile');return null;}
        return profile;
    }
    const api={validate,request,ensure,domains};
    if(typeof module!=='undefined') module.exports=api;
    if(typeof window!=='undefined')window.VisualAILearningProfile=api;
    if(typeof document==='undefined' || !document.getElementById('profile-form'))return;
    const auth=window.VisualAIAuth,form=document.getElementById('profile-form'),status=document.getElementById('profile-status'),save=document.getElementById('profile-save');
    const get=id=>document.getElementById(id);
    domains.forEach((domain,i)=>{
        const label=document.createElement('label'),input=document.createElement('input'),span=document.createElement('span');
        label.className='interest-chip';input.type='checkbox';input.name='interest';input.value=domain;
        span.textContent=icons[i]+' '+domain;label.append(input,span);get('profile-interests').append(label);
        input.addEventListener('change',()=>{get('custom-interest-row').hidden=!form.querySelector('input[value="Other"]').checked;});
    });
    async function load() {
        save.disabled=true;status.textContent='Loading your learning profile…';
        try {
            const profile=await request(auth);const prefs=profile.preferences;
            get('profile-name').value=profile.display_name || '';
            if(prefs){get('profile-level').value=prefs.education_level;get('profile-language').value=prefs.preferred_language;get('profile-goal').value=prefs.learning_goal;get('profile-personalize').checked=prefs.personalization_enabled;get('profile-custom').value=prefs.custom_interest;form.querySelectorAll('input[name="interest"]').forEach(input=>input.checked=prefs.interested_domains.includes(input.value));get('custom-interest-row').hidden=!prefs.interested_domains.includes('Other');}
            get('profile-cancel').hidden=!profile.complete;
            status.textContent=profile.complete?'Edit preferences for future generated resources. Your saved resources stay unchanged.':'Select at least one interested domain to continue.';
            save.disabled=false;
        }catch(error){status.textContent=error.message;get('profile-retry').hidden=false;}
    }
    get('profile-retry').addEventListener('click',()=>{get('profile-retry').hidden=true;void load();});
    form.addEventListener('submit',async event=>{
        event.preventDefault();if(save.disabled)return;
        const interests=Array.from(form.querySelectorAll('input[name="interest"]:checked')).map(input=>input.value);
        const value={display_name:get('profile-name').value.trim() || null,education_level:get('profile-level').value,interested_domains:interests,custom_interest:interests.includes('Other')?get('profile-custom').value.trim():'',preferred_language:get('profile-language').value,learning_goal:get('profile-goal').value,personalization_enabled:get('profile-personalize').checked};
        const error=validate(value);if(error){status.textContent=error;get('profile-interests').focus();return;}
        save.disabled=true;status.textContent='Saving your profile…';
        try{const result=await request(auth,'PUT',value);if(!result.complete)throw Error('Profile is incomplete. Select an interest.');window.location.assign('/dashboard');}
        catch(error){status.textContent=error.message;save.disabled=false;}
    });
    get('profile-logout').addEventListener('click',()=>auth.logout());void load();
})();
