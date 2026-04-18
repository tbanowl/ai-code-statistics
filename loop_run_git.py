import subprocess
            
for i in range(0, 100):
    # cmd = ['git', 'rev-parse', "--show-toplevel"]
    cmd = ['git-ai', 'status']
    print(f"execute times: {i}")
    env = {}
    result = subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )