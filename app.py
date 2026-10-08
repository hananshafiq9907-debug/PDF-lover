from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
import fitz
from pathlib import Path
import zipfile, uuid, shutil, re, secrets

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 150 * 1024 * 1024
BASE = Path(__file__).resolve().parent
UPLOADS, OUTPUT = BASE/'uploads', BASE/'output'
UPLOADS.mkdir(exist_ok=True); OUTPUT.mkdir(exist_ok=True)
IMAGE_EXTENSIONS = {'jpg','jpeg','png','webp','bmp','tiff','tif'}

def allowed(name, exts):
    return '.' in name and name.rsplit('.',1)[1].lower() in exts

def job_dirs():
    job=uuid.uuid4().hex; u=UPLOADS/job; o=OUTPUT/job
    u.mkdir(); o.mkdir(); return job,u,o

def cleanup(job):
    shutil.rmtree(UPLOADS/job, ignore_errors=True); shutil.rmtree(OUTPUT/job, ignore_errors=True)

@app.get('/')
def index(): return render_template('index.html')

@app.post('/api/image-to-pdf')
def image_to_pdf():
    files=request.files.getlist('images')
    if not files: return jsonify(error='No images uploaded.'),400
    job,u,o=job_dirs()
    try:
        page_size=request.form.get('page_size','A4'); orientation=request.form.get('orientation','portrait')
        fit_mode=request.form.get('fit','contain'); margin_mm=max(0,min(float(request.form.get('margin','10')),20))
        quality=request.form.get('quality','high')
        jpeg_quality={'high':92,'medium':78,'small':55}.get(quality,92)
        sizes={'A4':(210,297),'A5':(148,210),'Letter':(215.9,279.4),'Legal':(215.9,355.6)}
        fixed=None
        if page_size in sizes:
            wmm,hmm=sizes[page_size]
            if orientation=='landscape': wmm,hmm=hmm,wmm
            fixed=(wmm*72/25.4,hmm*72/25.4)
        order=[x for x in request.form.get('order','').split(',') if x.strip().isdigit()]
        indexed={str(i):f for i,f in enumerate(files)}
        ordered=[indexed[i] for i in order if i in indexed]
        ordered += [f for f in files if f not in ordered]
        doc=fitz.open()
        for idx,file in enumerate(ordered):
            if not file.filename or not allowed(file.filename,IMAGE_EXTENSIONS): continue
            path=u/f'{idx:04d}_{secure_filename(file.filename)}'; file.save(path)
            with Image.open(path) as src:
                im=ImageOps.exif_transpose(src).convert('RGB')
                tmp=u/f'img_{idx}.jpg'; im.save(tmp,'JPEG',quality=jpeg_quality,optimize=True)
                data=tmp.read_bytes(); iw,ih=im.size
                if fixed:
                    pw,ph=fixed; page=doc.new_page(width=pw,height=ph)
                    margin=margin_mm*72/25.4
                    box=fitz.Rect(margin,margin,pw-margin,ph-margin)
                    sx,sy=box.width/iw,box.height/ih
                    scale=max(sx,sy) if fit_mode=='cover' else min(sx,sy)
                    if fit_mode=='original': scale=min(1,sx,sy)
                    rw,rh=iw*scale,ih*scale
                    rect=fitz.Rect(box.x0+(box.width-rw)/2,box.y0+(box.height-rh)/2,box.x0+(box.width+rw)/2,box.y0+(box.height+rh)/2)
                    page.insert_image(rect,stream=data)
                else:
                    page=doc.new_page(width=iw*72/150,height=ih*72/150)
                    page.insert_image(page.rect,stream=data)
        if len(doc)==0: raise ValueError('No supported images found.')
        out=o/'converted.pdf'; doc.save(out,garbage=4,deflate=True); doc.close()
        return send_file(out,as_attachment=True,download_name='converted-images.pdf')
    except Exception as e:
        cleanup(job); return jsonify(error=str(e)),500

@app.post('/api/pdf-info')
def pdf_info():
    pdf=request.files.get('pdf')
    if not pdf or not pdf.filename or not allowed(pdf.filename,{'pdf'}): return jsonify(error='Invalid PDF.'),400
    job,u,o=job_dirs()
    try:
        path=u/secure_filename(pdf.filename); pdf.save(path); doc=fitz.open(path)
        info={'pages':len(doc),'title':doc.metadata.get('title',''),'author':doc.metadata.get('author','')}; doc.close(); cleanup(job)
        return jsonify(info)
    except Exception as e: cleanup(job); return jsonify(error=str(e)),400

@app.post('/api/pdf-to-image')
def pdf_to_image():
    pdf=request.files.get('pdf')
    if not pdf or not pdf.filename or not allowed(pdf.filename,{'pdf'}): return jsonify(error='Please upload a PDF.'),400
    job,u,o=job_dirs()
    try:
        path=u/secure_filename(pdf.filename); pdf.save(path); doc=fitz.open(path)
        fmt=request.form.get('format','png').lower(); fmt=fmt if fmt in {'png','jpg','webp'} else 'png'
        dpi=max(72,min(int(request.form.get('dpi','150')),300)); selected=request.form.get('pages','all').strip().lower()
        if selected in {'','all'}: indices=list(range(len(doc)))
        else:
            indices=[]
            for part in selected.split(','):
                m=re.fullmatch(r'\s*(\d+)\s*(?:-\s*(\d+)\s*)?',part)
                if not m: continue
                a=int(m.group(1)); b=int(m.group(2) or a)
                for n in range(min(a,b),max(a,b)+1):
                    if 1<=n<=len(doc) and n-1 not in indices: indices.append(n-1)
            indices.sort()
        if not indices: raise ValueError('No valid PDF pages were selected.')
        paths=[]; matrix=fitz.Matrix(dpi/72,dpi/72)
        for oi,pi in enumerate(indices,1):
            pix=doc[pi].get_pixmap(matrix=matrix,alpha=False); out=o/f'page_{oi:03d}.{fmt}'
            if fmt=='png': pix.save(out)
            else:
                im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples); im.save(out,fmt.upper(),quality=92); im.close()
            paths.append(out)
        doc.close()
        if len(paths)==1: return send_file(paths[0],as_attachment=True,download_name=paths[0].name)
        z=o/'pdf-pages.zip'
        with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as archive:
            for p in paths: archive.write(p,p.name)
        return send_file(z,as_attachment=True,download_name='pdf-pages.zip')
    except Exception as e:
        cleanup(job); return jsonify(error=str(e)),500


@app.post('/api/pdf-protect')
def pdf_protect():
    pdf=request.files.get('pdf')
    password=request.form.get('password','')
    confirm=request.form.get('confirm','')
    if not pdf or not pdf.filename or not allowed(pdf.filename,{'pdf'}):
        return jsonify(error='Please upload a PDF.'),400
    if len(password) < 4:
        return jsonify(error='Password must be at least 4 characters.'),400
    if password != confirm:
        return jsonify(error='Passwords do not match.'),400

    job,u,o=job_dirs()
    try:
        path=u/secure_filename(pdf.filename)
        pdf.save(path)
        doc=fitz.open(path)
        if doc.needs_pass:
            raise ValueError('This PDF is already password protected. Unlock it first, then protect it with the new password.')

        # Build permissions from the user's choices. Accessibility remains enabled
        # so assistive technology can read protected documents.
        permissions=fitz.PDF_PERM_ACCESSIBILITY
        for field, flag in (
            ('allow_print', fitz.PDF_PERM_PRINT),
            ('allow_copy', fitz.PDF_PERM_COPY),
            ('allow_modify', fitz.PDF_PERM_MODIFY),
            ('allow_annotate', fitz.PDF_PERM_ANNOTATE),
            ('allow_forms', fitz.PDF_PERM_FORM),
            ('allow_assemble', fitz.PDF_PERM_ASSEMBLE),
            ('allow_high_quality', fitz.PDF_PERM_PRINT_HQ),
        ):
            if request.form.get(field) == '1':
                permissions |= flag

        out=o/'protected.pdf'
        owner_password=secrets.token_urlsafe(24)
        doc.save(
            out,
            garbage=4,
            deflate=True,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            permissions=permissions,
            owner_pw=owner_password,
            user_pw=password,
            preserve_metadata=1
        )
        doc.close()
        return send_file(out, as_attachment=True, download_name='protected.pdf')
    except Exception as e:
        cleanup(job)
        return jsonify(error=str(e)),400

@app.errorhandler(413)
def too_large(_): return jsonify(error='Maximum upload size is 150 MB.'),413

if __name__=='__main__': app.run(debug=True,host='127.0.0.1',port=8000)
