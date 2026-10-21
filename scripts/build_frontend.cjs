// No framework migration: validate and build the existing vanilla ES-module application.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),source=path.join(root,'frontend'),output=path.join(source,'dist');
const manifest=[];
function walk(directory){
 for(const entry of fs.readdirSync(directory,{withFileTypes:true})){
  const file=path.join(directory,entry.name);if(entry.isDirectory()){if(!['dist','node_modules'].includes(entry.name))walk(file);continue;}
  if(!/\.(html|css|js|mjs)$/.test(entry.name)||entry.name.includes('.test.')||entry.name.startsWith('test-'))continue;
  const text=fs.readFileSync(file,'utf8');
  if(/\.(js|mjs)$/.test(file)){
   const check=spawnSync(process.execPath,['--check',file],{encoding:'utf8'});
   if(check.status!==0)throw Error('JavaScript syntax check failed: '+path.relative(source,file));
  }
  // Imports resolve from the module; src/href in markup a script renders resolve from the page at the frontend root.
  const links=[...text.matchAll(/(?:from\s*|import\s*)['"](\.[^'"]+)['"]|(?:src|href)=["']([^"'#]+)["']/g)].map(m=>m[1]?[m[1],path.dirname(file)]:[m[2],/\.(js|mjs)$/.test(file)?source:path.dirname(file)]);
  for(let [target,base] of links){if(target.includes('${'))continue;if(/^(https?:|data:|mailto:|tel:|\/)/.test(target))continue;target=target.split(/[?#]/)[0];if(target&&!fs.existsSync(path.resolve(base,target)))throw Error(`Missing frontend dependency: ${path.relative(source,file)} -> ${target}`);}
  const rel=path.relative(source,file),dest=path.join(output,rel);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.copyFileSync(file,dest);
  manifest.push({file:rel.replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(text).digest('hex')});
 }
}
walk(source);fs.writeFileSync(path.join(output,'build-manifest.json'),JSON.stringify({entry:'index.html',demo:'prototype.html',files:manifest},null,2));
console.log(`Built ${manifest.length} validated static assets in frontend/dist. No API keys or environment files bundled.`);
