// No framework migration: validate and build the existing vanilla ES-module application.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),source=path.join(root,'frontend'),output=path.join(source,'dist');
const manifest=[];
require('esbuild').buildSync({entryPoints:[path.join(source,'js/supabase-entry.mjs')],bundle:true,format:'esm',platform:'browser',target:'es2022',minify:true,outfile:path.join(source,'vendor/supabase.mjs')});
function walk(directory){
 for(const entry of fs.readdirSync(directory,{withFileTypes:true})){
  const file=path.join(directory,entry.name);if(entry.isDirectory()){if(!['dist','node_modules'].includes(entry.name))walk(file);continue;}
  if(!/\.(html|css|js|mjs|svg|png|jpe?g|webp|gif|ico|woff2?|ttf)$/.test(entry.name)||entry.name.includes('.test.')||entry.name.startsWith('test-'))continue;
  if(!/\.(html|css|js|mjs)$/.test(entry.name)){
    const bytes=fs.readFileSync(file),rel=path.relative(source,file),dest=path.join(output,rel);
    fs.mkdirSync(path.dirname(dest),{recursive:true});fs.copyFileSync(file,dest);
    manifest.push({file:rel.replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(bytes).digest('hex')});continue;
  }
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
walk(source);
const {LANNPYA_SUPABASE_URL:supabaseUrl,LANNPYA_SUPABASE_PUBLISHABLE_KEY:supabaseKey,LANNPYA_API_BASE_URL:apiBase}=process.env;
if(supabaseUrl||supabaseKey||apiBase){
 if(!supabaseUrl||!supabaseKey||!apiBase)throw Error('Set all three public auth build variables, or use the secure server runtime.');
 const validKey=supabaseKey.startsWith('sb_publishable_')||(()=>{try{return JSON.parse(Buffer.from(supabaseKey.split('.')[1],'base64url').toString()).role==='anon';}catch{return false;}})();
 if(!validKey)throw Error('Only a Supabase publishable/anon key may enter a frontend build.');
 const text='globalThis.LANNPYA_RUNTIME='+JSON.stringify({mode:'SUPABASE_BACKEND',supabaseUrl,supabaseKey,apiBase})+';\n';
 fs.writeFileSync(path.join(output,'runtime-config.js'),text);
 manifest.find(item=>item.file==='runtime-config.js').sha256=crypto.createHash('sha256').update(text).digest('hex');
}
fs.writeFileSync(path.join(output,'build-manifest.json'),JSON.stringify({entry:'index.html',demo:'prototype.html',files:manifest},null,2));
console.log(`Built ${manifest.length} validated static assets in frontend/dist. Only public auth configuration can be bundled.`);
