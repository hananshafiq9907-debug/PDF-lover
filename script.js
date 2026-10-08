const $=s=>document.querySelector(s);let files=[],pdfFile=null;
function msg(t,error=false){const s=$('#status');s.textContent=t;s.classList.remove('hidden');s.style.borderColor=error?'var(--danger)':''}
function resetMsg(){$('#status').classList.add('hidden')}
function setupDrop(zone,input,handler){['dragenter','dragover'].forEach(e=>zone.addEventListener(e,x=>{x.preventDefault();zone.classList.add('drag')}));['dragleave','drop'].forEach(e=>zone.addEventListener(e,x=>{x.preventDefault();zone.classList.remove('drag')}));zone.addEventListener('drop',e=>handler([...e.dataTransfer.files]));input.addEventListener('change',()=>handler([...input.files]));zone.addEventListener('click',e=>{if(e.target.tagName!=='BUTTON')input.click()})}
function render(){const list=$('#pages');list.innerHTML='';$('#pageCount').textContent=`${files.length} page${files.length===1?'':'s'}`;files.forEach((f,i)=>{const c=document.createElement('article');c.className='page';c.draggable=true;c.dataset.i=i;c.innerHTML=`<span class="number">${i+1}</span><button class="remove-page">×</button><img src="${URL.createObjectURL(f)}"><div class="page-body"><div class="page-name" title="${f.name}">${f.name}</div><div class="page-tools"><button class="left">↶</button><button class="right">↷</button></div></div>`;c.querySelector('.remove-page').onclick=()=>{files.splice(i,1);render()};c.querySelector('.left').onclick=()=>rotate(c,-90);c.querySelector('.right').onclick=()=>rotate(c,90);c.addEventListener('dragstart',e=>e.dataTransfer.setData('text/plain',i));c.addEventListener('dragover',e=>e.preventDefault());c.addEventListener('drop',e=>{e.preventDefault();const from=+e.dataTransfer.getData('text/plain');const [x]=files.splice(from,1);files.splice(i,0,x);render()});list.appendChild(c)});$('#imageDrop').classList.toggle('hidden',files.length>0);$('#editor').classList.toggle('hidden',files.length===0)}
function rotate(card,deg){const img=card.querySelector('img'),canvas=document.createElement('canvas'),ctx=canvas.getContext('2d'),src=new Image();src.onload=()=>{const swap=Math.abs(deg)%180===90;canvas.width=swap?src.height:src.width;canvas.height=swap?src.width:src.height;ctx.translate(canvas.width/2,canvas.height/2);ctx.rotate(deg*Math.PI/180);ctx.drawImage(src,-src.width/2,-src.height/2);canvas.toBlob(blob=>{const old=files[+card.dataset.i];files[+card.dataset.i]=new File([blob],old.name,{type:'image/jpeg'});render()})};src.src=img.src}
setupDrop($('#imageDrop'),$('#images'),fs=>{files.push(...fs.filter(f=>f.type.startsWith('image/')||/\.(tif|tiff)$/i.test(f.name)));render();resetMsg()});$('#pickImages').onclick=e=>{e.stopPropagation();$('#images').click()};$('#add').onclick=()=>$('#images').click();$('#clear').onclick=()=>{files=[];$('#images').value='';render();resetMsg()};$('#margin').oninput=e=>$('#marginOut').value=e.target.value;
$('#makePdf').onclick=async()=>{if(!files.length)return;const fd=new FormData();files.forEach(f=>fd.append('images',f));fd.append('order',files.map((_,i)=>i).join(','));fd.append('page_size',$('#pageSize').value);fd.append('orientation',$('#orientation').value);fd.append('fit',$('#fit').value);fd.append('margin',$('#margin').value);fd.append('quality',$('#quality').value);msg('Building PDF…');try{const r=await fetch('/api/image-to-pdf',{method:'POST',body:fd});if(!r.ok)throw Error((await r.json()).error||'Conversion failed');download(await r.blob(),'converted-images.pdf');msg('PDF created successfully.')}catch(e){msg(e.message,true)}};
setupDrop($('#pdfDrop'),$('#pdf'),fs=>{const f=fs.find(x=>x.type==='application/pdf'||/\.pdf$/i.test(x.name));if(!f)return msg('Please choose a PDF.',true);pdfFile=f;$('#pdfName').textContent=f.name;$('#pdfMeta').textContent=formatBytes(f.size);$('#pdfDrop').classList.add('hidden');$('#pdfEditor').classList.remove('hidden');loadInfo(f)});$('#pickPdf').onclick=e=>{e.stopPropagation();$('#pdf').click()};async function loadInfo(f){const fd=new FormData();fd.append('pdf',f);try{const r=await fetch('/api/pdf-info',{method:'POST',body:fd}),x=await r.json();if(r.ok)$('#pdfMeta').textContent=`${x.pages} page${x.pages===1?'':'s'} · ${formatBytes(f.size)}`}catch{}}
$('#makeImages').onclick=async()=>{if(!pdfFile)return;const fd=new FormData();fd.append('pdf',pdfFile);fd.append('pages',$('#pagesSelect').value);fd.append('format',$('#format').value);fd.append('dpi',$('#dpi').value);msg('Rendering PDF pages…');try{const r=await fetch('/api/pdf-to-image',{method:'POST',body:fd});if(!r.ok)throw Error((await r.json()).error||'Conversion failed');const b=await r.blob();download(b,b.type==='application/zip'?'pdf-pages.zip':`page-1.${$('#format').value}`);msg('Conversion complete.')}catch(e){msg(e.message,true)}};
document.querySelectorAll('.mode').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.mode').forEach(x=>x.classList.remove('active'));b.classList.add('active');
 const mode=b.dataset.mode;
 $('#imageMode').classList.toggle('hidden',mode!=='image');
 $('#pdfMode').classList.toggle('hidden',mode!=='pdf');
 $('#protectMode').classList.toggle('hidden',mode!=='protect');
 $('#title').textContent=mode==='image'?'Images → PDF':mode==='pdf'?'PDF → Images':'PDF Protector';
 $('#subtitle').textContent=mode==='image'?'Build a polished PDF from your images.':mode==='pdf'?'Render selected PDF pages into image files.':'Password-protect a PDF with AES-256 encryption.';
 resetMsg();
});$('#theme').onclick=()=>document.documentElement.classList.toggle('light');function download(blob,name){const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}function formatBytes(n){if(!n)return'0 B';const u=['B','KB','MB','GB'],i=Math.floor(Math.log(n)/Math.log(1024));return`${(n/1024**i).toFixed(i?1:0)} ${u[i]}`}

let protectFile=null;
setupDrop($('#protectDrop'),$('#protectPdf'),fs=>{
 const f=fs.find(x=>x.type==='application/pdf'||/\.pdf$/i.test(x.name));
 if(!f)return msg('Please choose a PDF.',true);
 protectFile=f;$('#protectName').textContent=f.name;$('#protectMeta').textContent=formatBytes(f.size);
 $('#protectDrop').classList.add('hidden');$('#protectEditor').classList.remove('hidden');resetMsg();
});
$('#pickProtect').onclick=e=>{e.stopPropagation();$('#protectPdf').click()};
$('#protectButton').onclick=async()=>{
 if(!protectFile)return;
 const password=$('#protectPassword').value,confirm=$('#protectConfirm').value;
 if(password.length<4)return msg('Password must be at least 4 characters.',true);
 if(password!==confirm)return msg('Passwords do not match.',true);
 const fd=new FormData();fd.append('pdf',protectFile);fd.append('password',password);fd.append('confirm',confirm);
 [['allowPrint','#allowPrint'],['allowHighQuality','#allowHighQuality'],['allowCopy','#allowCopy'],['allowModify','#allowModify'],['allowAnnotate','#allowAnnotate'],['allowForms','#allowForms'],['allowAssemble','#allowAssemble']]
   .forEach(([k,s])=>{if($(s).checked)fd.append(k,'1')});
 msg('Protecting PDF with AES-256…');
 try{
   const r=await fetch('/api/pdf-protect',{method:'POST',body:fd});
   if(!r.ok)throw Error((await r.json()).error||'Protection failed');
   download(await r.blob(),'protected.pdf');msg('PDF protected successfully.');
 }catch(e){msg(e.message,true)}
};
