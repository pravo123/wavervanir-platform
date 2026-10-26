const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(path.join(__dirname,'../src/wavervanir_api/web/index.html'),'utf8');
const auth=html.slice(html.indexOf('async function authFetch('),html.indexOf('// ---- auth UI ----'));
const boot=html.slice(html.indexOf('// ---- boot ----'),html.indexOf('</script>',html.indexOf('// ---- boot ----'))).replace('applyStatic();\nvoid boot();','');
const defer=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}};
const response=(status,body={})=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
function setup(fetch){
  const nodes={},events=[];
  const store={a:'synthetic-A',r:'synthetic-RA',set(a,r){this.a=a;this.r=r},clear(){this.a=null;this.r=null}};
  const c={store,fetch,AbortController,setTimeout,clearTimeout,Error,$:id=>nodes[id]??=( {classList:{add(){},remove(){}},onclick:null}),show:s=>events.push(s),setMode(){},enterTerminal:u=>events.push('terminal:'+u.id),clearPanes(){}};
  vm.createContext(c);vm.runInContext(auth+'\n'+boot,c);
  return {c,store,events,nodes};
}
(async()=>{
  const checks=[];
  async function test(name,fn){await fn();checks.push({name,passed:true})}
  await test('temporary account failure preserves session and offers retry',async()=>{
    const x=setup(async()=>response(503));await x.c.boot();assert.equal(x.store.a,'synthetic-A');assert.deepEqual(x.events,['connection']);
  });
  await test('network failure preserves session and offers retry',async()=>{
    const x=setup(async()=>{throw new Error('synthetic network outage')});await x.c.boot();assert.equal(x.store.r,'synthetic-RA');assert.deepEqual(x.events,['connection']);
  });
  await test('successful retry opens same account without new login',async()=>{
    let fail=true;const x=setup(async()=>fail?response(503):response(200,{id:'A'}));await x.c.boot();fail=false;await x.nodes.connectionRetry.onclick();assert.equal(x.events.at(-1),'terminal:A');assert.equal(x.store.a,'synthetic-A');
  });
  await test('actual denied refresh returns to login and clears invalid tokens',async()=>{
    const x=setup(async()=>response(401));await x.c.boot();assert.equal(x.store.a,null);assert.equal(x.events.at(-1),'auth');
  });
  await test('refresh service outage is not an invalid session',async()=>{
    const x=setup(async url=>response(url==='/auth/refresh'?503:401));await x.c.boot();assert.equal(x.store.a,'synthetic-A');assert.equal(x.events.at(-1),'connection');
  });
  await test('sign-out while account body is pending cannot reopen terminal',async()=>{
    const body=defer(),started=defer();const x=setup(async()=>({status:200,ok:true,json(){started.resolve();return body.promise}}));const pending=x.c.boot();await started.promise;x.nodes.connectionSignout.onclick();body.resolve({id:'A'});await pending;assert(!x.events.some(s=>s.startsWith('terminal:')));assert.equal(x.store.a,null);
  });
  await test('late refresh cannot restore credentials after sign-out',async()=>{
    const pending=defer(),started=defer();const x=setup(async()=>{started.resolve();return pending.promise});const request=x.c.tryRefresh();await started.promise;x.store.clear();pending.resolve(response(200,{access_token:'A2',refresh_token:'RA2'}));assert.equal(await request,false);assert.equal(x.store.a,null);
  });
  await test('concurrent expired requests share the refresh',async()=>{
    const pending=defer(),started=defer();let refreshes=0;const x=setup(async()=>{refreshes++;started.resolve();return pending.promise});const a=x.c.tryRefresh(),b=x.c.tryRefresh();await started.promise;pending.resolve(response(200,{access_token:'A2',refresh_token:'RA2'}));assert.deepEqual(await Promise.all([a,b]),[true,true]);assert.equal(refreshes,1);
  });
  console.log(JSON.stringify({checks:checks.length,passed:checks.length,scope:'Actual inline authentication and boot functions with controlled network/storage boundaries; synthetic accounts only',cases:checks}));
})().catch(error=>{console.error(error);process.exitCode=1});
