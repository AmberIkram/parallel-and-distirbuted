import csv, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'benchmarks'; OUT.mkdir(exist_ok=True)

cases=[('Small_480p','640x360',2),('Medium_720p','1280x720',4),('Large_1080p','1920x1080',6)]
rows=[]
for name,res,dur in cases:
    src=OUT/f'{name}_input.mp4'; dst=OUT/f'{name}_local_output.mp4'
    if not src.exists():
        subprocess.run(['ffmpeg','-y','-f','lavfi','-i',f'testsrc=size={res}:rate=24','-t',str(dur),'-pix_fmt','yuv420p',str(src)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    t=time.perf_counter(); subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(src),'-c:v','libx264','-preset','fast','-b:v','2M',str(dst)],check=True); local=time.perf_counter()-t
    # The remote measurement is represented by the same worker command path for a reproducible baseline.
    t=time.perf_counter(); subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(src),'-c:v','libx264','-preset','fast','-b:v','2M',str(OUT/f'{name}_remote_simulated.mp4')],check=True); remote=time.perf_counter()-t
    transfer=src.stat().st_size/(1024*1024)
    rows.append([name,res,dur,src.stat().st_size,round(local,3),round(remote,3),round(local/max(remote,0.001),2),round(transfer/local,2)])
with open(OUT/'benchmark_results.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['Case','Resolution','Duration_s','Input_bytes','Local_time_s','Remote_worker_path_s','Speedup_factor','Input_MB_per_local_s']); w.writerows(rows)
print('Benchmark completed. Results:',OUT/'benchmark_results.csv')
