// Shareable evidence: never export cookies, headers, form bodies, URLs with buyer tokens or raw traces.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),source=path.join(root,'test-results/browser-results.json');
const report=JSON.parse(fs.readFileSync(source,'utf8')),cases=[];
function visit(suite){
 for(const spec of suite.specs||[])for(const test of spec.tests||[]){
   const result=test.results.at(-1),attachment=result.attachments?.find(a=>a.name==='sanitized-browser-observations');
   const observations=attachment?.body?JSON.parse(Buffer.from(attachment.body,'base64').toString()):null;
   cases.push({name:spec.title,status:result.status,duration_ms:result.duration,observations});
 }
 for(const child of suite.suites||[])visit(child);
}
visit(report);
const directory=path.join(root,'docs/visual-testing'),screenshotDir=path.join(directory,'screenshots');
const screenshots=fs.readdirSync(screenshotDir).filter(f=>f.endsWith('.png')).sort().map(file=>{
 const bytes=fs.readFileSync(path.join(screenshotDir,file));return {file:'screenshots/'+file,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)};
});
const result={generated_at:new Date().toISOString(),source:'Real Playwright Chromium; isolated loopback FastAPI processes and temporary SQLite per test',
 stats:report.stats,cases,screenshots};
const destination=process.argv[2]?path.resolve(root,process.argv[2]):path.join(directory,'BROWSER_OBSERVATIONS.json');
if(!destination.startsWith(root+path.sep))throw Error('Report must stay inside this worktree');
fs.mkdirSync(path.dirname(destination),{recursive:true});
if(path.dirname(destination)!==directory)for(const entry of result.screenshots)entry.file=path.relative(path.dirname(destination),path.join(directory,entry.file)).replaceAll('\\','/');
fs.writeFileSync(destination,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({passed:cases.filter(t=>t.status==='passed').length,failed:cases.filter(t=>t.status==='failed'||t.status==='timedOut').length,
 screenshots:screenshots.length,page_errors:cases.reduce((n,c)=>n+(c.observations?.errors.length||0),0),duration_ms:report.stats.duration}));
