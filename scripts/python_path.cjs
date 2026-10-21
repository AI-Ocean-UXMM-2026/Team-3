const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
function pythonPath(){
 if(process.env.LANNPYA_PYTHON){if(!fs.existsSync(process.env.LANNPYA_PYTHON))throw Error('LANNPYA_PYTHON does not identify an executable');return process.env.LANNPYA_PYTHON;}
 const relative=process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python';
 const local=path.join(root,'backend',relative);if(fs.existsSync(local))return local;
 // A sibling worktree may already have the installed project environment; no secrets are read.
 const worktrees=spawnSync('git',['worktree','list','--porcelain'],{cwd:root,encoding:'utf8'});
 for(const m of (worktrees.stdout||'').matchAll(/^worktree (.+)$/gm)){const candidate=path.join(m[1].trim(),'backend',relative);if(fs.existsSync(candidate))return candidate;}
 const create=spawnSync(process.platform==='win32'?'py':'python3',process.platform==='win32'?['-3','-m','venv',path.dirname(path.dirname(local))]:['-m','venv',path.dirname(path.dirname(local))],{stdio:'inherit'});
 if(create.status!==0)throw Error('Python virtual environment could not be created');
 const install=spawnSync(local,['-m','pip','install','-r',path.join(root,'backend/requirements-dev.lock')],{stdio:'inherit'});
 if(install.status!==0)throw Error('Pinned backend dependency installation failed');return local;
}
module.exports={pythonPath,root};
