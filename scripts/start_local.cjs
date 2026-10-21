const {spawn}=require('node:child_process');
const path=require('node:path');
const {pythonPath,root}=require('./python_path.cjs');
require('./build_frontend.cjs');
const args=process.argv.slice(2);
const child=spawn(pythonPath(),['-m','tools.integrated_workspace',...args],{cwd:path.join(root,'backend'),stdio:'inherit',windowsHide:true});
child.on('error',()=>{console.error('Unable to start the local integration backend.');process.exitCode=1;});
child.on('exit',code=>{process.exitCode=code??1;});
// The console forwards Ctrl+C to Python as well; let Uvicorn shut down its contexts.
process.on('SIGINT',()=>{if(process.platform!=='win32')child.kill('SIGINT');});
