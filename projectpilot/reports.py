"""Dependency-free, paginated PDF reports using standard PDF fonts (WinAnsi)."""
from datetime import datetime
from pathlib import Path
import textwrap

WIDTHS=[761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 761, 278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584, 761, 556, 761, 222, 556, 333, 1000, 556, 556, 333, 1000, 667, 333, 1000, 761, 611, 761, 761, 222, 222, 333, 333, 350, 556, 1000, 333, 1000, 500, 333, 944, 761, 500, 667, 278, 333, 556, 556, 556, 556, 260, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 556, 537, 278, 333, 333, 365, 556, 834, 834, 834, 611, 667, 667, 667, 667, 667, 667, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 500, 556, 556, 556, 556, 278, 278, 278, 278, 556, 556, 556, 556, 556, 556, 556, 584, 611, 556, 556, 556, 556, 500, 556, 500]

def wrap_line(value):
    value=str(value).replace("\n"," ").encode("cp1252",errors="replace").decode("cp1252")
    result=[]
    while value:
        width=0;cut=0
        for ch in value:
            step=WIDTHS[ch.encode("cp1252")[0]]*11/1000
            if width+step>523:break
            width+=step;cut+=1
        if cut<len(value):
            space=value.rfind(" ",0,cut+1)
            if space>0:cut=space
        result.append(value[:cut]);value=value[cut:].lstrip()
    return result or [""]

def _pdf_string(value):
    result=''
    for b in str(value).encode('cp1252',errors='replace'):
        if b in (40,41,92):result+='\\'+chr(b)
        elif b<32 or b>=127:result+=f'\\{b:03o}'
        else:result+=chr(b)
    return '('+result+')'

def write_pdf(path,title,rows,author):
    lines=[]
    for row in rows or ['No matching records in this view.']:
        lines += wrap_line(row) or ['']
        lines.append('')
    pages=[lines[i:i+42] for i in range(0,len(lines),42)]
    objects=[b'',b'',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>']
    kids=[]
    for index,chunk in enumerate(pages):
        commands=['0.08 0.10 0.17 rg 0 752 595 90 re f','0.4 0.36 0.85 rg 36 750 523 4 re f',f'BT /F2 19 Tf 1 1 1 rg 36 800 Td {_pdf_string(title)} Tj ET',f'BT /F1 10 Tf 0.75 0.8 0.9 rg 36 775 Td {_pdf_string("3.0.1 | "+author[:32]+" | "+datetime.now().strftime("%Y-%m-%d %H:%M"))} Tj ET']
        y=720
        for line in chunk:
            if line:commands.append(f'BT /F1 11 Tf 0.1 0.14 0.22 rg 36 {y} Td {_pdf_string(line)} Tj ET')
            y-=15
        commands += ['0.85 0.87 0.92 RG 36 62 m 559 62 l S',f'BT /F1 9 Tf 0.4 0.45 0.53 rg 36 43 Td {_pdf_string("Local workspace | "+str(index+1)+" / "+str(len(pages)))} Tj ET']
        stream='\n'.join(commands).encode('ascii');pid=len(objects)+1;cid=pid+1;kids.append(f'{pid} 0 R');objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {cid} 0 R >>'.encode());objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
    objects[0]=b'<< /Type /Catalog /Pages 2 0 R >>';objects[1]=f'<< /Type /Pages /Count {len(pages)} /Kids [{" ".join(kids)}] >>'.encode()
    pdf=bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n');offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(pdf));pdf+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    start=len(pdf);pdf+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    for pos in offsets[1:]:pdf+=f'{pos:010d} 00000 n \n'.encode()
    pdf+=f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode();Path(path).write_bytes(pdf)
