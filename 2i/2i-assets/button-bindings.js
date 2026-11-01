/* Use normal script bindings for controls; inline HTML handlers may be blocked. */
'use strict';
for(const button of document.querySelectorAll('[data-toggle-section]'))button.onclick=()=>toggleSection(button.dataset.toggleSection);
for(const button of document.querySelectorAll('[data-close-modal]'))button.onclick=()=>closeModal(button.dataset.closeModal);
for(const button of document.querySelectorAll('[data-close-reference]'))button.onclick=()=>closeRefViewer();
for(const button of document.querySelectorAll('[data-reference-search]'))button.onclick=()=>filterRefs();
for(const button of document.querySelectorAll('.ref-tab[data-filter]'))button.onclick=()=>setRefFilter(button,button.dataset.filter);
let deleteReferenceDialog;
function confirmReferenceDelete(id){
  const reference=references.find(item=>item.id===id);if(!reference)return;
  if(!deleteReferenceDialog){
    deleteReferenceDialog=photoModal('refDeleteDialog','Delete reference');
    const label=document.createElement('p');label.id='refDeleteName';deleteReferenceDialog.body.append(label);
    const remove=document.createElement('button');remove.id='refDeleteConfirm';remove.className='mc-btn';remove.textContent='Delete reference';deleteReferenceDialog.actions.append(remove);
  }
  $('refDeleteName').textContent='Delete “'+reference.name+'” from this manuscript?';
  $('refDeleteConfirm').onclick=()=>{deleteReference(id);closeModal('refDeleteDialog');};openModal('refDeleteDialog');
}
