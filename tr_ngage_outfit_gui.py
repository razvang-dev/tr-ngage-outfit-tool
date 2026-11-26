#!/usr/bin/env python3
"""Tk GUI for TR N-Gage Outfit Tool v0.4.0. No third-party modules."""
from pathlib import Path
import json, threading, os, sys, subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tr_ngage_outfit as core

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"TR N-Gage Outfit Tool v{core.VERSION}")
        self.geometry("840x650"); self.minsize(720,560)
        nb=ttk.Notebook(self); nb.pack(fill='both',expand=True,padx=8,pady=8)
        self.wad_tab=ttk.Frame(nb); self.wad2_tab=ttk.Frame(nb); self.tex_tab=ttk.Frame(nb); self.examples_tab=ttk.Frame(nb)
        nb.add(self.wad_tab,text='Classic WAD'); nb.add(self.wad2_tab,text='WAD2 Lab'); nb.add(self.tex_tab,text='Texture Editor'); nb.add(self.examples_tab,text='Examples')
        self._build_wad_tab(); self._build_wad2_tab(); self._build_tex_tab(); self._build_examples_tab()

    def _browse_file(self,var,types):
        p=filedialog.askopenfilename(filetypes=types)
        if p: var.set(p)
    def _browse_dir(self,var):
        p=filedialog.askdirectory()
        if p: var.set(p)
    def _open_dir(self,p):
        p=Path(p) if p else None
        if not p or not p.exists(): return
        try:
            if sys.platform.startswith('win'): os.startfile(str(p))
            elif sys.platform=='darwin': subprocess.Popen(['open',str(p)])
            else: subprocess.Popen(['xdg-open',str(p)])
        except Exception: pass
    def _entryrow(self,parent,row,label,var,command,types=None):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='e',padx=7,pady=5)
        ttk.Entry(parent,textvariable=var).grid(row=row,column=1,sticky='ew',padx=4,pady=5)
        if types is None: cmd=lambda:self._browse_dir(var)
        else: cmd=lambda:self._browse_file(var,types)
        ttk.Button(parent,text='Browse…',command=cmd).grid(row=row,column=2,padx=7,pady=5)
        parent.columnconfigure(1,weight=1)
    def _run(self,button,log,func,done_message):
        button.config(state='disabled'); log.insert('end','\nWorking…\n'); log.see('end')
        def worker():
            try: result=func(); err=None
            except Exception as e: result=None; err=e
            self.after(0,lambda:self._done(button,log,result,err,done_message))
        threading.Thread(target=worker,daemon=True).start()
    def _done(self,button,log,result,err,done_message):
        button.config(state='normal')
        if err:
            log.insert('end',f'ERROR: {err}\n'); log.see('end'); messagebox.showerror('Operation failed',str(err)); return
        log.insert('end',json.dumps(result,indent=2)+'\nSUCCESS\n'); log.see('end'); messagebox.showinfo('Complete',done_message)

    def _build_wad_tab(self):
        f=self.wad_tab; self.wad=tk.StringVar(); self.lara=tk.StringVar(); self.out=tk.StringVar(); self.weapon=tk.BooleanVar(False)
        ttk.Label(f,text='Hardware-proven classic WAD → N-Gage outfit conversion',font=('TkDefaultFont',10,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',padx=8,pady=(10,4))
        self._entryrow(f,1,'Classic WAD (.wad):',self.wad,None,[('Classic Tomb Raider WAD','*.wad'),('All files','*')])
        self._entryrow(f,2,'N-Gage lara.mesh:',self.lara,None,[('lara.mesh','*.mesh'),('All files','*')])
        self._entryrow(f,3,'Output folder:',self.out,None,None)
        ttk.Checkbutton(f,text='Experimental: map compatible weapon/holster variant faces',variable=self.weapon).grid(row=4,column=1,columnspan=2,sticky='w',padx=4,pady=4)
        bar=ttk.Frame(f); bar.grid(row=5,column=0,columnspan=3,sticky='ew',padx=8,pady=4)
        ttk.Button(bar,text='Analyze',command=self.analyze_wad).pack(side='left',padx=(0,8))
        self.wad_convert=ttk.Button(bar,text='Convert',command=self.convert_wad); self.wad_convert.pack(side='left')
        ttk.Button(bar,text='Open output',command=lambda:self._open_dir(self.out.get())).pack(side='right')
        self.wad_log=tk.Text(f,wrap='word',height=20); self.wad_log.grid(row=6,column=0,columnspan=3,sticky='nsew',padx=8,pady=8); f.rowconfigure(6,weight=1)
        self.wad_log.insert('end','Choose a compatible classic WAD and the original N-Gage lara.mesh.\n')
    def analyze_wad(self):
        try:
            if not Path(self.wad.get()).is_file() or not Path(self.lara.get()).is_file(): raise core.ToolError('Choose valid WAD and lara.mesh files')
            wad=core.parse_classic_wad(Path(self.wad.get())); ng=core.parse_ngage_lara(Path(self.lara.get())); c=core.find_lara_skin(wad,ng)
            result={'detected_lara_mesh_pointer_start':c['start'],'vertex_count_matches':c['vertex_count_matches'],'topology_matches':c['topology_matches'],'topology_total':c['topology_total'],'topology_coverage':c['topology_matches']/max(1,c['topology_total'])}
            self.wad_log.insert('end','\nANALYSIS\n'+json.dumps(result,indent=2)+'\n'); self.wad_log.see('end')
        except Exception as e: messagebox.showerror('Analyze failed',str(e))
    def convert_wad(self):
        def work():
            if not Path(self.wad.get()).is_file(): raise core.ToolError('Choose a valid WAD')
            if not Path(self.lara.get()).is_file(): raise core.ToolError('Choose a valid lara.mesh')
            if not self.out.get(): raise core.ToolError('Choose an output folder')
            return core.convert(Path(self.wad.get()),Path(self.lara.get()),Path(self.out.get()),map_weapon_variants=self.weapon.get())
        self._run(self.wad_convert,self.wad_log,work,'Generated new_tpage.tpa and retexture.dat. Back up your originals before installing them.')

    def _build_wad2_tab(self):
        f=self.wad2_tab
        ttk.Label(f,text='Tomb Editor WAD2 → N-Gage Lara pipeline',font=('TkDefaultFont',10,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',padx=8,pady=(10,4))
        ttk.Label(f,text='Analyze first. Grade A/B outfits can use the texture/topology converter. v0.4 adds an EXPERIMENTAL geometry serializer for Grade C sources; use it as a laboratory build until the runtime patch is finished.',wraplength=760,justify='left').grid(row=1,column=0,columnspan=3,sticky='w',padx=8,pady=(0,8))
        self.w2file=tk.StringVar(); self.w2lara=tk.StringVar(); self.w2out=tk.StringVar(); self.w2obj=tk.StringVar(); self.w2fallback=tk.StringVar(value='auto')
        self._entryrow(f,2,'Tomb Editor WAD2:',self.w2file,None,[('Tomb Editor WAD2','*.wad2'),('All files','*')])
        self._entryrow(f,3,'N-Gage lara.mesh:',self.w2lara,None,[('lara.mesh','*.mesh'),('All files','*')])
        self._entryrow(f,4,'Output folder:',self.w2out,None,None)
        ttk.Label(f,text='Object ID override (optional):').grid(row=5,column=0,sticky='e',padx=7,pady=5)
        ttk.Entry(f,textvariable=self.w2obj,width=12).grid(row=5,column=1,sticky='w',padx=4,pady=5)
        ttk.Label(f,text='Unmatched face fallback:').grid(row=6,column=0,sticky='e',padx=7,pady=5)
        ttk.Combobox(f,textvariable=self.w2fallback,values=['auto','classic','uniform'],state='readonly',width=14).grid(row=6,column=1,sticky='w',padx=4,pady=5)
        ttk.Label(f,text='auto completes fully-opaque single-color skins (Gold/Midas) across head/torso and weapon variants.',wraplength=470,justify='left').grid(row=6,column=2,sticky='w',padx=4,pady=5)
        bar=ttk.Frame(f);bar.grid(row=7,column=0,columnspan=3,sticky='ew',padx=8,pady=6)
        self.w2_analyze_btn=ttk.Button(bar,text='Analyze WAD2',command=self.analyze_wad2);self.w2_analyze_btn.pack(side='left',padx=(0,8))
        self.w2_convert_btn=ttk.Button(bar,text='Convert Compatible Outfit',command=self.convert_wad2);self.w2_convert_btn.pack(side='left',padx=(0,8))
        self.w2_export_btn=ttk.Button(bar,text='Export Geometry Lab',command=self.export_wad2_model);self.w2_export_btn.pack(side='left',padx=(0,8))
        self.w2_geom_btn=ttk.Button(bar,text='Build EXP Geometry',command=self.build_wad2_geometry);self.w2_geom_btn.pack(side='left')
        ttk.Button(bar,text='Open output',command=lambda:self._open_dir(self.w2out.get())).pack(side='right')
        self.w2_log=tk.Text(f,wrap='word',height=20);self.w2_log.grid(row=8,column=0,columnspan=3,sticky='nsew',padx=8,pady=8);f.rowconfigure(8,weight=1)
        self.w2_log.insert('end','WAD2 v0.4.0 adds automatic uniform-source completion for Gold/Midas-style skins. Analyze classifies the outfit before any game files are generated.\n')

    def _wad2_args(self):
        if not Path(self.w2file.get()).is_file(): raise core.ToolError('Choose a valid WAD2 file')
        if not Path(self.w2lara.get()).is_file(): raise core.ToolError('Choose a valid lara.mesh')
        obj=None
        if self.w2obj.get().strip():
            try: obj=int(self.w2obj.get().strip(),0)
            except ValueError: raise core.ToolError('Object ID must be a decimal or 0x-prefixed integer')
        return Path(self.w2file.get()),Path(self.w2lara.get()),obj

    def analyze_wad2(self):
        def work():
            w,l,obj=self._wad2_args(); return core.analyze_wad2_file(w,l,obj)
        self._run(self.w2_analyze_btn,self.w2_log,work,'WAD2 analysis complete. Grade A/B is texture-convertible; Grade C should use Geometry Lab export.')

    def convert_wad2(self):
        def work():
            w,l,obj=self._wad2_args()
            if not self.w2out.get(): raise core.ToolError('Choose an output folder')
            return core.convert_wad2(w,l,Path(self.w2out.get()),obj,fallback_mode=self.w2fallback.get())
        self._run(self.w2_convert_btn,self.w2_log,work,'Generated WAD2-based new_tpage.tpa and retexture.dat. Back up originals before testing.')

    def export_wad2_model(self):
        def work():
            w,l,obj=self._wad2_args()
            if not self.w2out.get(): raise core.ToolError('Choose an output folder')
            return core.export_wad2_model(w,l,Path(self.w2out.get()),obj)
        self._run(self.w2_export_btn,self.w2_log,work,'Exported WAD2 Lara OBJ parts and source textures for geometry development. These are not installable game files.')

    def build_wad2_geometry(self):
        if not messagebox.askyesno('Experimental geometry serializer','This output changes Lara topology and is NOT safe for ordinary levels yet. Continue building the special-path laboratory bundle?'):
            return
        def work():
            w,l,obj=self._wad2_args()
            if not self.w2out.get(): raise core.ToolError('Choose an output folder')
            return core.build_wad2_geometry(w,l,Path(self.w2out.get()),obj)
        self._run(self.w2_geom_btn,self.w2_log,work,'Generated experimental lara.mesh + matching texture/retexture files. Read EXPERIMENTAL-NOTICE.txt before testing.')

    def _build_tex_tab(self):
        f=self.tex_tab
        ttk.Label(f,text='Export existing N-Gage textures for editing — no WAD required',font=('TkDefaultFont',10,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',padx=8,pady=(10,4))
        self.xtpa=tk.StringVar(); self.xrt=tk.StringVar(); self.xlara=tk.StringVar(); self.xwork=tk.StringVar()
        self._entryrow(f,1,'new_tpage.tpa:',self.xtpa,None,[('N-Gage TPA','*.tpa'),('All files','*')])
        self._entryrow(f,2,'retexture.dat:',self.xrt,None,[('retexture.dat','*.dat'),('All files','*')])
        self._entryrow(f,3,'lara.mesh:',self.xlara,None,[('lara.mesh','*.mesh'),('All files','*')])
        self._entryrow(f,4,'Workspace folder:',self.xwork,None,None)
        self.export_btn=ttk.Button(f,text='Export Editable Texture',command=self.export_tex); self.export_btn.grid(row=5,column=1,sticky='w',padx=4,pady=6)
        ttk.Button(f,text='Open workspace',command=lambda:self._open_dir(self.xwork.get())).grid(row=5,column=2,padx=7,pady=6)
        ttk.Separator(f,orient='horizontal').grid(row=6,column=0,columnspan=3,sticky='ew',padx=8,pady=8)
        ttk.Label(f,text='Import edited 256×256 PNG/BMP and rebuild game files',font=('TkDefaultFont',10,'bold')).grid(row=7,column=0,columnspan=3,sticky='w',padx=8,pady=(4,4))
        self.iwork=tk.StringVar(); self.iimg=tk.StringVar(); self.iout=tk.StringVar(); self.alt=tk.StringVar(value='duplicate')
        self._entryrow(f,8,'Workspace folder:',self.iwork,None,None)
        self._entryrow(f,9,'Edited image:',self.iimg,None,[('Editable texture','*.png *.bmp'),('PNG','*.png'),('BMP','*.bmp'),('All files','*')])
        self._entryrow(f,10,'Output folder:',self.iout,None,None)
        ttk.Label(f,text='Alternate palette bank:').grid(row=11,column=0,sticky='e',padx=7,pady=5)
        ttk.Combobox(f,textvariable=self.alt,values=['duplicate','preserve'],state='readonly',width=14).grid(row=11,column=1,sticky='w',padx=4,pady=5)
        self.import_btn=ttk.Button(f,text='Import Edited Texture',command=self.import_tex); self.import_btn.grid(row=12,column=1,sticky='w',padx=4,pady=6)
        ttk.Button(f,text='Open output',command=lambda:self._open_dir(self.iout.get())).grid(row=12,column=2,padx=7,pady=6)
        self.tex_log=tk.Text(f,wrap='word',height=12); self.tex_log.grid(row=13,column=0,columnspan=3,sticky='nsew',padx=8,pady=8); f.rowconfigure(13,weight=1)
        self.tex_log.insert('end','Export creates texture_edit.png / .bmp plus masks and metadata. Edit the image without resizing it, then import it back.\n')

    def _build_examples_tab(self):
        f=self.examples_tab
        ttk.Label(f,text='Hardware/in-game diagnostic examples for the stock AoD outfit',font=('TkDefaultFont',10,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',padx=8,pady=(10,4))
        ttk.Label(f,text='These examples demonstrate why mesh-level edits are too coarse and why pelvis/belt separation needs face/texture-level control.',wraplength=760,justify='left').grid(row=1,column=0,columnspan=3,sticky='w',padx=8,pady=(0,8))
        self.etpa=tk.StringVar(); self.ert=tk.StringVar(); self.elara=tk.StringVar(); self.eout=tk.StringVar()
        self._entryrow(f,2,'Stock AoD new_tpage.tpa:',self.etpa,None,[('N-Gage TPA','*.tpa'),('All files','*')])
        self._entryrow(f,3,'Stock AoD retexture.dat:',self.ert,None,[('retexture.dat','*.dat'),('All files','*')])
        self._entryrow(f,4,'Reference lara.mesh:',self.elara,None,[('lara.mesh','*.mesh'),('All files','*')])
        self._entryrow(f,5,'Output folder:',self.eout,None,None)
        bar=ttk.Frame(f);bar.grid(row=6,column=0,columnspan=3,sticky='ew',padx=8,pady=6)
        self.ex1_btn=ttk.Button(bar,text='Generate Example 1: Arm/Body Contrast',command=lambda:self.generate_example('arm-body-contrast',self.ex1_btn));self.ex1_btn.pack(side='left',padx=(0,8))
        self.ex2_btn=ttk.Button(bar,text='Generate Example 2: Pants + Belt Isolation',command=lambda:self.generate_example('pants-belt-isolation',self.ex2_btn));self.ex2_btn.pack(side='left')
        ttk.Button(bar,text='Open included examples',command=lambda:self._open_dir(Path(__file__).resolve().parent/'examples')).pack(side='right')
        self.examples_log=tk.Text(f,wrap='word',height=19);self.examples_log.grid(row=7,column=0,columnspan=3,sticky='nsew',padx=8,pady=8);f.rowconfigure(7,weight=1)
        self.examples_log.insert('end',
            'Example 1 leaves the pelvis untouched: the shorts remain and visually hide the belt separation.\n\n'
            'Example 2 keeps the pelvis as one mesh but changes its faces independently: the main shorts/pants faces use the arm/skin descriptor while the upper belt/waistband faces retain their original descriptors.\n\n'
            'This distinction—mesh object vs. face/texture mapping—is now documented under docs/BODY-ACCESSORY-SEPARATION.md.\n')

    def generate_example(self,preset,button):
        def work():
            for v,n in [(self.etpa,'stock AoD new_tpage.tpa'),(self.ert,'stock AoD retexture.dat'),(self.elara,'lara.mesh')]:
                if not Path(v.get()).is_file(): raise core.ToolError(f'Choose a valid {n}')
            if not self.eout.get(): raise core.ToolError('Choose an output folder')
            out=Path(self.eout.get())/preset
            return core.make_diagnostic_example(preset,Path(self.etpa.get()),Path(self.ert.get()),Path(self.elara.get()),out)
        self._run(button,self.examples_log,work,'Diagnostic files generated. Use the INSTALL folder inside the preset output; back up originals first.')

    def export_tex(self):
        def work():
            for v,n in [(self.xtpa,'new_tpage.tpa'),(self.xrt,'retexture.dat'),(self.xlara,'lara.mesh')]:
                if not Path(v.get()).is_file(): raise core.ToolError(f'Choose a valid {n}')
            if not self.xwork.get(): raise core.ToolError('Choose a workspace folder')
            r=core.export_texture_workspace(Path(self.xtpa.get()),Path(self.xrt.get()),Path(self.xlara.get()),Path(self.xwork.get()))
            if not self.iwork.get(): self.iwork.set(self.xwork.get())
            if not self.iimg.get(): self.iimg.set(str(Path(self.xwork.get())/'texture_edit.png'))
            return r
        self._run(self.export_btn,self.tex_log,work,'Editable texture workspace created. Open texture_edit.png in your photo editor; do not resize it.')
    def import_tex(self):
        def work():
            if not self.iwork.get() or not Path(self.iwork.get()).is_dir(): raise core.ToolError('Choose a valid exported workspace folder')
            img=Path(self.iimg.get()) if self.iimg.get() else None
            if img is not None and not img.is_file(): raise core.ToolError('Choose a valid edited PNG/BMP')
            if not self.iout.get(): raise core.ToolError('Choose an output folder')
            return core.import_texture_workspace(Path(self.iwork.get()),img,Path(self.iout.get()),self.alt.get())
        self._run(self.import_btn,self.tex_log,work,'Rebuilt new_tpage.tpa and retexture.dat. Back up your originals before installing them.')

if __name__=='__main__': App().mainloop()
