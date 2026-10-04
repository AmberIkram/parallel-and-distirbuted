import os, socket, threading, time, uuid, queue, sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from common.protocol import recv_file, recv_json, send_file, send_json, sha256_file, make_handshake

class ClientApp:
    def __init__(self, root):
        self.root=root; root.title('Distributed Render Offloader'); root.geometry('1050x720'); root.minsize(900,620)
        self.q=queue.Queue(); self.build_ui(); self.poll()

    def build_ui(self):
        style=ttk.Style();
        try: style.theme_use('clam')
        except: pass
        top=ttk.Frame(self.root,padding=18); top.pack(fill='x')
        ttk.Label(top,text='DISTRIBUTED RENDER OFFLOADER',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(top,text='Client dashboard • LAN socket • checksum validation • live progress',font=('Segoe UI',10)).pack(anchor='w',pady=(3,0))
        cfg=ttk.LabelFrame(self.root,text='Connection & Job Configuration',padding=14); cfg.pack(fill='x',padx=18,pady=10)
        for c in range(4): cfg.columnconfigure(c,weight=1)
        self.ip=tk.StringVar(value='127.0.0.1'); self.port=tk.StringVar(value='5050'); self.file=tk.StringVar(); self.res=tk.StringVar(value='1280x720'); self.br=tk.StringVar(value='2M'); self.preset=tk.StringVar(value='fast')
        fields=[('Server IP',self.ip),('Port',self.port),('Resolution',self.res),('Bitrate',self.br)]
        for i,(lab,var) in enumerate(fields):
            ttk.Label(cfg,text=lab).grid(row=0,column=i,sticky='w',padx=5); ttk.Entry(cfg,textvariable=var).grid(row=1,column=i,sticky='ew',padx=5)
        ttk.Label(cfg,text='Input Video').grid(row=2,column=0,sticky='w',padx=5,pady=(10,0)); ttk.Entry(cfg,textvariable=self.file).grid(row=3,column=0,columnspan=3,sticky='ew',padx=5); ttk.Button(cfg,text='Browse',command=self.browse).grid(row=3,column=3,sticky='ew',padx=5)
        ttk.Label(cfg,text='Preset').grid(row=4,column=0,sticky='w',padx=5,pady=(10,0)); ttk.Combobox(cfg,textvariable=self.preset,values=['ultrafast','fast','medium','slow','p1','p2','p3','p4'],state='readonly').grid(row=5,column=0,sticky='ew',padx=5)
        self.status=tk.StringVar(value='Disconnected'); ttk.Label(cfg,textvariable=self.status).grid(row=5,column=1,sticky='w',padx=5)
        ttk.Button(cfg,text='CHECK CONNECTION',command=self.check).grid(row=5,column=2,sticky='ew',padx=5); ttk.Button(cfg,text='SUBMIT REMOTE JOB',command=self.submit).grid(row=5,column=3,sticky='ew',padx=5)
        body=ttk.Frame(self.root,padding=(18,0)); body.pack(fill='both',expand=True)
        left=ttk.LabelFrame(body,text='Live Progress',padding=14); left.pack(side='left',fill='both',expand=True,padx=(0,8))
        self.pb=ttk.Progressbar(left,mode='determinate',maximum=100); self.pb.pack(fill='x',pady=(4,12)); self.pct=tk.StringVar(value='0%'); ttk.Label(left,textvariable=self.pct,font=('Segoe UI',16,'bold')).pack(anchor='center')
        self.log=tk.Text(left,height=20,bg='#111827',fg='#d1d5db',insertbackground='white',font=('Consolas',10),relief='flat'); self.log.pack(fill='both',expand=True,pady=(12,0)); self.write('Client ready. Configure the remote worker and submit a video job.\n')
        right=ttk.LabelFrame(body,text='Worker Status',padding=14,width=280); right.pack(side='right',fill='y')
        self.worker=tk.StringVar(value='Unknown'); self.gpu=tk.StringVar(value='Not checked'); self.lat=tk.StringVar(value='—'); self.integrity=tk.StringVar(value='Pending')
        for label,var in [('Worker',self.worker),('GPU/NVENC',self.gpu),('Latency',self.lat),('File Integrity',self.integrity)]:
            ttk.Label(right,text=label,font=('Segoe UI',9,'bold')).pack(anchor='w',pady=(8,2)); ttk.Label(right,textvariable=var,wraplength=220).pack(anchor='w')

    def write(self,msg): self.log.insert('end',msg); self.log.see('end')
    def browse(self):
        p=filedialog.askopenfilename(filetypes=[('Video files','*.mp4 *.mov *.mkv *.avi'),('All files','*.*')]);
        if p:self.file.set(p)
    def check(self): threading.Thread(target=self._check,daemon=True).start()
    def _check(self):
        t=time.perf_counter(); s=None
        try:
            s=socket.create_connection((self.ip.get(),int(self.port.get())),timeout=5); hello=recv_json(s); send_json(s,make_handshake('client')); ack=recv_json(s); ms=(time.perf_counter()-t)*1000
            self.q.put(('status',f'Connected • {ms:.1f} ms')); self.q.put(('worker', 'READY')); self.q.put(('gpu',f"{'NVIDIA NVENC available' if hello.get('nvenc') else 'CPU fallback / NVENC unavailable'}")); self.q.put(('lat',f'{ms:.1f} ms'))
            s.close()
        except Exception as e:self.q.put(('status',f'Connection failed: {e}'))
    def submit(self): threading.Thread(target=self._submit,daemon=True).start()
    def _submit(self):
        path=self.file.get()
        if not path or not os.path.isfile(path): self.q.put(('error','Select a valid input video first.')); return
        try:
            self.q.put(('reset',None)); t0=time.perf_counter(); s=socket.create_connection((self.ip.get(),int(self.port.get())),timeout=15); hello=recv_json(s); send_json(s,make_handshake('client')); recv_json(s)
            job=uuid.uuid4().hex[:10]; size=os.path.getsize(path); digest=sha256_file(path); name=Path(path).name
            send_json(s,{'type':'job','job_id':job,'filename':name,'size':size,'sha256':digest,'resolution':self.res.get(),'bitrate':self.br.get(),'preset':self.preset.get()})
            recv_json(s); self.q.put(('log',f'Handshake OK • worker GPU={hello.get("gpu")} NVENC={hello.get("nvenc")}'))
            self.q.put(('log',f'Uploading {name} • SHA-256 {digest[:16]}…'))
            send_file(s,path); verify=recv_json(s); self.q.put(('integrity','VERIFIED')); self.q.put(('log',f'Upload verified • {verify.get("sha256","")[:16]}…'))
            while True:
                msg=recv_json(s); typ=msg.get('type')
                if typ=='progress': self.q.put(('progress',msg.get('percent',0))); self.q.put(('log',f'Remote render progress: {msg.get("percent",0)}%'))
                elif typ=='render_complete': self.expected_output_sha = msg.get('sha256'); self.q.put(('log',f'Render complete • codec={msg.get("codec")} • {msg.get("size")} bytes'))
                elif typ=='output_ready':
                    out=ROOT/'client_output'; out.mkdir(exist_ok=True); target=out/f'{job}_rendered.mp4'; recv_file(s,target,msg['size']);
                    actual_sha=sha256_file(target)
                    if getattr(self, 'expected_output_sha', None) and actual_sha != self.expected_output_sha:
                        raise RuntimeError('Output checksum mismatch after download')
                    self.q.put(('integrity','OUTPUT VERIFIED')); self.q.put(('progress',100)); self.q.put(('log',f'Output saved: {target}')); self.q.put(('status',f'Completed in {time.perf_counter()-t0:.2f}s')); break
                elif typ=='error': raise RuntimeError(msg.get('message','Remote worker error'))
            s.close()
        except Exception as e:self.q.put(('error',str(e)))
    def poll(self):
        try:
            while True:
                typ,val=self.q.get_nowait()
                if typ=='progress': self.pb['value']=val; self.pct.set(f'{val:.1f}%')
                elif typ=='log': self.write(val+'\n')
                elif typ=='status': self.status.set(val); self.write(val+'\n')
                elif typ=='worker': self.worker.set(val)
                elif typ=='gpu': self.gpu.set(val)
                elif typ=='lat': self.lat.set(val)
                elif typ=='integrity': self.integrity.set(val)
                elif typ=='reset': self.pb['value']=0; self.pct.set('0%')
                elif typ=='error': self.write('ERROR: '+val+'\n'); messagebox.showerror('Job Error',val)
        except queue.Empty: pass
        self.root.after(150,self.poll)

if __name__=='__main__':
    root=tk.Tk(); ClientApp(root); root.mainloop()
