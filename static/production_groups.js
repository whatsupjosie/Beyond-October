(async function(){
'use strict';
const $=id=>document.getElementById(id);let groups=[],people=[],me=null,canCreate=false;
const message=m=>{$('status').textContent=m;};
async function api(path,body,method){const response=await fetch(path,{method:method||(body?'POST':'GET'),headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Production request failed');return data;}
function edit(){
 const group=groups.find(g=>g.id===$('groups').value),members=new Map((group?.members||[]).map(m=>[m.user_id,m]));
 const allowed=canCreate||group?.members.some(m=>m.user_id===me&&m.role==='producer');
 $('name').value=group?.name||'';$('members').replaceChildren();
 for(const person of people){
  const row=document.createElement('label');row.className='member';row.dataset.user=person.user_id;
  const checked=document.createElement('input');checked.type='checkbox';checked.checked=members.has(person.user_id)||(!group&&person.user_id===me);checked.className='included';checked.setAttribute('aria-label','Include '+person.display_name);
  const name=document.createElement('span');name.textContent=person.display_name+' · '+person.user_id;
  const department=document.createElement('input');department.type='text';department.maxLength=60;department.placeholder='Department';department.setAttribute('aria-label','Department for '+person.display_name);department.className='department';department.value=members.get(person.user_id)?.department||'';
  const role=document.createElement('select');role.className='role';role.setAttribute('aria-label','Production role for '+person.display_name);role.add(new Option('Member','member'));role.add(new Option('Producer','producer'));role.value=members.get(person.user_id)?.role||'member';
  row.append(checked,name,department,role);$('members').append(row);
 }
 for(const element of $('editor').elements)element.disabled=!allowed;
 if(!allowed)message('You can view this production. Its host or producer manages membership.');
}
async function load(selected=''){
 const data=await api('/api/production/groups'),roster=await api('/api/production/people');groups=data.groups;people=roster.people;me=roster.me;canCreate=data.can_create;
 $('groups').replaceChildren();if(canCreate)$('groups').add(new Option('New production',''));for(const g of groups)$('groups').add(new Option(g.name,g.id));
 $('groups').value=selected||(!canCreate&&groups.length?groups[0].id:'');edit();
}
$('groups').onchange=edit;
$('editor').onsubmit=async event=>{event.preventDefault();$('save').disabled=true;try{
 const current=groups.find(g=>g.id===$('groups').value);
 const body={name:$('name').value,members:[...document.querySelectorAll('.member')].filter(row=>row.querySelector('.included').checked).map(row=>({user_id:row.dataset.user,department:row.querySelector('.department').value,role:row.querySelector('.role').value}))};
 if(current)body.revision=current.revision;
 const result=await api('/api/production/groups'+(current?'/'+current.id:''),body,current?'PATCH':'POST');await load(result.id);message('Production saved. Notes use this membership immediately.');
 }catch(e){message(e.message);}finally{$('save').disabled=false;}};
try{const session=await ReachAuth.requireSession(location.pathname);if(session)await load();}catch(e){message(e.message);}
})();
