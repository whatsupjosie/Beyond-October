(function(){
'use strict';
const $=id=>document.getElementById(id),query=new URLSearchParams(location.search);
const fields=[
 ['real_name','Name, if you want to share it',80],['nickname','Nickname',80],['pronouns','Pronouns',80],['city','City or where you are from',120],
 ['experience','Professional, hobbyist or learner','experience'],['bio','About you',4000],['education','Education',2000],['skills','Skills',2000],
 ['resume','Résumé',4000],['hobbies','Hobbies',2000],['favorite_books','Favorite books',2000],['favorite_movies','Favorite movies',2000],
 ['favorite_podcasts','Favorite podcasts',2000],['internet_recommendations','Internet hangouts and recommendations',2000],
 ['current_projects','What you are working on',2000],['dream_project','Your dream project',2000],['collaborations','Collaborations you would like',2000],
 ['website','Website','url'],['portfolio','Portfolio','url'],['linkedin','LinkedIn','url'],['reel','Demo reel link','url']
];
let profile=null,dirty=false,busy=false,draftTimer=null;
const status=message=>{$('status').textContent=message;};
async function api(path,options={}){
 const response=await fetch(path,{cache:'no-store',...options});let data;
 try{data=await response.json();}catch(_){throw Error('The host returned an unreadable response');}
 if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Profile request failed ('+response.status+')');
 return data;
}
function lock(value){busy=value;for(const e of $('editor').elements)e.disabled=value;}
function draftKey(){return 'pubcast.profile.draft.'+profile.user_id;}
function values(){
 const about={};for(const [key]of fields){const value=$('field-'+key).value;if(value)about[key]=value;}
 const shared=fields.filter(([key])=>$('share-'+key).checked).map(([key])=>key);if($('sharePhoto').checked)shared.push('photo');
 return {display_name:$('displayName').value,email:$('email').value,
  details:{discoverable:$('visibility').value==='discoverable',public_fields:shared,about,onboarding_complete:true},revision:profile.revision};
}
function fill(data){
 $('displayName').value=data.display_name||'';$('email').value=data.email||'';
 const d=data.details||{};$('visibility').value=d.discoverable?'discoverable':'private';
 for(const [key]of fields){$('field-'+key).value=d.about?.[key]||'';$('share-'+key).checked=(d.public_fields||[]).includes(key);}
 $('sharePhoto').checked=(d.public_fields||[]).includes('photo');
}
function draft(){
 if(!profile||busy)return;dirty=true;clearTimeout(draftTimer);draftTimer=setTimeout(()=>{
  try{sessionStorage.setItem(draftKey(),JSON.stringify(values()));status('Unsaved draft kept in this tab.');}
  catch(_){status('This tab could not keep a draft. Save your profile before leaving.');}
 },250);
}
function buildFields(){
 for(const [key,label,kind]of fields){
  const box=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=label;box.append(legend);
  const input=document.createElement(kind==='experience'?'select':typeof kind==='number'&&kind>120?'textarea':'input');input.id='field-'+key;input.setAttribute('aria-label',label);
  if(kind==='experience')for(const [value,text]of [['','Skip'],['professional','Professional'],['hobbyist','Hobbyist'],['learner','Learner']])input.add(new Option(text,value));
  else {input.maxLength=kind==='url'?2048:kind;if(input.tagName==='INPUT')input.type=kind==='url'?'url':'text';}
  const share=document.createElement('label');share.className='share';const check=document.createElement('input');check.type='checkbox';check.id='share-'+key;
  share.append(check,document.createTextNode('Share this field on my discoverable card'));box.append(input,share);$('fields').append(box);
 }
}
function safeLink(value){try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u:null;}catch(_){return null;}}
function showCard(card){
 const target=$('card');target.replaceChildren();target.hidden=false;
 const title=document.createElement('h2');title.textContent=card.display_name;target.append(title);
 const id=document.createElement('p');id.className='identity';id.textContent=card.user_id;target.append(id);
 if(card.has_photo){const image=document.createElement('img');image.id='cardPhoto';image.alt='Profile picture';image.src='/api/profiles/'+encodeURIComponent(card.user_id)+'/photo';target.append(image);}
 for(const [key,value]of Object.entries(card.about||{})){
  const label=fields.find(f=>f[0]===key)?.[1]||key;const row=document.createElement('p');const name=document.createElement('strong');name.textContent=label+': ';row.append(name);
  const url=safeLink(value);
  if(['website','portfolio','linkedin','reel'].includes(key)&&url){
   const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=value;row.append(link);
   if(key==='reel'){
    let embed=null;const host=url.hostname.replace(/^www\./,'');
    const youtube=host==='youtu.be'?url.pathname.slice(1):['youtube.com','m.youtube.com'].includes(host)?url.searchParams.get('v'):null;
    if(youtube&&/^[A-Za-z0-9_-]{11}$/.test(youtube))embed='https://www.youtube-nocookie.com/embed/'+youtube;
    const vimeo=host==='vimeo.com'?url.pathname.slice(1):null;if(vimeo&&/^\d{1,20}$/.test(vimeo))embed='https://player.vimeo.com/video/'+vimeo;
    if(embed){const play=document.createElement('button');play.type='button';play.textContent='Load reel';play.onclick=()=>{
      const iframe=document.createElement('iframe');iframe.title='Demo reel';iframe.referrerPolicy='no-referrer';iframe.setAttribute('sandbox','allow-scripts allow-same-origin allow-presentation');iframe.allowFullscreen=true;iframe.src=embed;row.append(iframe);play.remove();
     };row.append(document.createElement('br'),play);}
   }
  }else row.append(document.createTextNode(value));target.append(row);
 }
}
function next(){
 try{const u=new URL(query.get('next')||'/foresight',location.origin);return u.origin===location.origin?u.pathname+u.search+u.hash:'/foresight';}
 catch(_){return '/foresight';}
}
async function save(optionalSkip=false){
 if(busy)return;
 try{if(dirty)sessionStorage.setItem(draftKey(),JSON.stringify(values()));}catch(_){status('Could not preserve your draft. Keep this tab open until saving succeeds.');}
 lock(true);clearTimeout(draftTimer);
 try{
  const body=values();if(optionalSkip)body.details={...profile.details,onboarding_complete:true};
  profile=await api('/api/profile/me',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  dirty=false;sessionStorage.removeItem(draftKey());status('Profile saved.');
  if(query.has('onboarding'))location.assign(next());
 }catch(error){status(error.message);}finally{lock(false);}
}
async function load(){
 const viewing=query.get('user');
 if(viewing){const card=await api('/api/profiles/'+encodeURIComponent(viewing));$('title').textContent='PubCast profile';$('intro').hidden=true;showCard(card);return;}
 profile=await api('/api/profile/me');$('identity').textContent=profile.user_id+' · '+profile.username;$('editor').hidden=false;
 fill(profile);$('skip').hidden=!query.has('onboarding');
 if(profile.has_photo){$('photo').src='/api/profiles/'+encodeURIComponent(profile.user_id)+'/photo';$('photo').hidden=false;}
 try{const kept=JSON.parse(sessionStorage.getItem(draftKey())||'null');if(kept){fill(kept);dirty=true;
  const stale=Number.isInteger(kept.revision)&&kept.revision!==profile.revision;
  if(Number.isInteger(kept.revision))profile.revision=kept.revision;
  status(stale?'Your draft was restored, but the host profile changed. Reload before saving.':'Your unsaved draft was restored. Save to update the host.');
 }}catch(_){status('A saved draft could not be opened. Your host profile is shown.');}
}
buildFields();$('editor').addEventListener('input',draft);$('editor').addEventListener('change',draft);
$('editor').onsubmit=e=>{e.preventDefault();save();};$('skip').onclick=()=>save(true);
$('reload').onclick=()=>{if(!dirty||confirm('Discard the unsaved draft and reload your profile?')){sessionStorage.removeItem(draftKey());dirty=false;load().catch(e=>status(e.message));}};
$('preview').onclick=()=>{const v=values(),shared=new Set(v.details.public_fields);showCard({...profile,display_name:v.display_name,about:Object.fromEntries(Object.entries(v.details.about).filter(([key])=>shared.has(key))),has_photo:profile.has_photo&&shared.has('photo')});};
$('photoFile').onchange=async()=>{
 const file=$('photoFile').files[0];if(!file||busy)return;
 try{if(dirty)sessionStorage.setItem(draftKey(),JSON.stringify(values()));}catch(_){status('Could not preserve your draft. Save your profile before uploading a picture.');return;}
 lock(true);clearTimeout(draftTimer);
 try{if(file.size>2*1024*1024)throw Error('Choose an image under 2 MB');
  const updated=await api('/api/profile/photo?revision='+profile.revision,{method:'POST',headers:{'Content-Type':file.type},body:await file.arrayBuffer()});
  profile.revision=updated.revision;profile.has_photo=true;
  if(dirty)sessionStorage.setItem(draftKey(),JSON.stringify(values()));
  $('photo').src='/api/profiles/'+encodeURIComponent(profile.user_id)+'/photo?r='+profile.revision;$('photo').hidden=false;status('Picture saved. Your other form fields are unchanged.');
 }catch(e){status(e.message);}finally{lock(false);}
};
$('searchForm').onsubmit=async e=>{e.preventDefault();try{const data=await api('/api/profiles?q='+encodeURIComponent($('search').value));$('results').replaceChildren();
 for(const card of data.profiles){const link=document.createElement('a');link.className='result';link.href='/static/human_profile.html?user='+encodeURIComponent(card.user_id);link.textContent=card.display_name+' · '+card.user_id;$('results').append(link);}
 if(!data.profiles.length)$('results').textContent='No discoverable profiles matched on this host.';
 }catch(error){status(error.message);}};
window.addEventListener('beforeunload',e=>{if(dirty){
 try{sessionStorage.setItem(draftKey(),JSON.stringify(values()));}catch(_){}
 e.preventDefault();e.returnValue='';
}});
load().catch(e=>status(e.message));
})();
