#!/usr/bin/env node
// Reusable smoke check. --full expands sampling to every question.
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert/strict');
const {pathToFileURL}=require('url');
const options={};
for(let i=2;i<process.argv.length;i++){
 const key=process.argv[i];
 if(key==='--full')options.full=true;
 else if(key==='--help'){console.log('node check_review.cjs --html FILE --transcript FILE --artifacts WORKDIR [--full] [--playwright-module PATH] [--channel chrome|chromium]');process.exit(0);}
 else if(['--html','--transcript','--artifacts','--playwright-module','--channel'].includes(key)&&process.argv[i+1])options[key.slice(2)]=process.argv[++i];
 else throw new Error('Unknown or missing argument: '+key);
}
for(const key of ['html','transcript','artifacts'])if(!options[key])throw new Error('Missing --'+key);
let playwright;
for(const modulePath of [options['playwright-module'],process.env.PLAYWRIGHT_MODULE,'playwright',
 path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'),
 path.join(os.homedir(),'.cache/interview-audio-review/browser/node_modules/playwright')].filter(Boolean)){
 try{playwright=require(modulePath);break;}catch(e){if(e.code!=='MODULE_NOT_FOUND')throw e;}
}
if(!playwright)throw new Error('Playwright is unavailable. Supply --playwright-module or install it as documented in SKILL.md (browser dependencies).');
(async()=>{
 const started=performance.now(),artifacts=path.resolve(options.artifacts);fs.mkdirSync(artifacts,{recursive:true});
 const channel=options.channel||'chrome';
 const browser=await playwright.chromium.launch(channel==='chromium'?{headless:true}:{channel,headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve(options.html)).href);
  await page.getByRole('heading',{name:'整体评价',exact:true}).waitFor();
  const data=JSON.parse(await page.locator('#review-data').textContent());
  const raw=fs.readFileSync(options.transcript,'utf8');
  const source=raw.split(/\r?\n/).flatMap((line,i)=>{
   const match=line.match(/^\[\d{2}:\d{2}:\d{2} -> \d{2}:\d{2}:\d{2}\] (.*)$/);
   return match?[{id:'l'+(i+1),text:match[1]}]:[];
  });
  assert.equal(JSON.parse(await page.locator('#raw-data').textContent()),raw);
  const rendered=await page.locator('.source-fragment').evaluateAll(nodes=>nodes.map(node=>({
   id:node.dataset.sourceId||node.id,text:node.querySelector('.fragment-text').textContent
  })));
  const reconstructed=[];
  for(const part of rendered){
   const prior=reconstructed[reconstructed.length-1];
   if(prior?.id===part.id)prior.text+=part.text;
   else reconstructed.push({...part});
  }
  assert.deepEqual(reconstructed,source);
  assert.equal(new Set(await page.locator('[id]').evaluateAll(nodes=>nodes.map(n=>n.id))).size,await page.locator('[id]').count());
  assert.equal(await page.locator('.transcript .segment').count(),data.paragraph_count);
  assert.equal(await page.locator('.fragment-time').first().evaluate(n=>getComputedStyle(n).display),'none');
  const questions=data.questions,indices=options.full?questions.map((_,i)=>i):[...new Set([0,Math.floor(questions.length/2),questions.length-1])];
  for(const i of indices){
   const q=questions[i];await page.locator('.contents-item[data-view="'+q.id+'"]').click();
   assert.equal(await page.locator('.contents-item[data-view="'+q.id+'"]').textContent(),`Q${q.number} ${q.title}`);
   const labels=await page.locator('.segment[data-q="'+q.id+'"] .turn-label').allTextContents();
   assert(labels.every(label=>new RegExp(`^Q${q.number}(提问|回答|说明|说话人待核)$`).test(label)));
   assert.equal(await page.locator('.contents-item[aria-current="page"]').getAttribute('data-view'),q.id);
   assert(await page.locator('.segment[data-q="'+q.id+'"]').evaluateAll(nodes=>nodes.every(node=>node.classList.contains('selected'))));
   assert.equal(await page.locator('.segment.selected:not([data-q="'+q.id+'"])').count(),0);
   assert.equal(await page.locator('.analysis h2').textContent(),q.title);
   for(const id of q.segment_ids)assert(await page.locator('#'+id).evaluate(n=>n.closest('.segment').classList.contains('selected')));
   assert.equal(await page.locator('#analysis-panel details,#analysis-panel summary,.question-footer,.evidence-list').count(),0);
   assert.deepEqual(await page.locator('.steps li strong').allTextContents(),q.steps.map(step=>step.title));
   assert.equal(await page.locator('.speech').textContent(),q.speech);
   assert.equal(await page.locator('.speech').evaluate(node=>node.checkVisibility()),true);
  }
  const first=questions[0],last=questions[questions.length-1];
  await page.locator('.segment[data-q="'+first.id+'"]').first().click();
  assert.equal(await page.locator('.contents-item[aria-current="page"]').getAttribute('data-view'),first.id);
  await page.locator('.segment[data-q="'+last.id+'"]').first().focus();
  await page.locator('.segment[data-q="'+last.id+'"]').first().press('Enter');
  assert.equal(await page.locator('.contents-item[aria-current="page"]').getAttribute('data-view'),last.id);
  await page.locator('#timestamp-toggle').click();
  assert.equal(await page.locator('.fragment-time').first().evaluate(n=>getComputedStyle(n).display),'inline');
  await page.locator('#timestamp-toggle').click();
  const searchText=source.find(s=>s.text.trim().length>=4)?.text.trim().slice(0,4);
  if(searchText){await page.locator('#search').fill(searchText);assert(await page.locator('.match').count()>0);await page.locator('#search').fill('');}
  await page.locator('.contents-item[data-view="overview"]').click();
  await page.getByRole('heading',{name:'整体评价',exact:true}).waitFor();
  await page.locator('.contents-item[data-view="'+last.id+'"]').focus();
  await page.locator('.contents-item[data-view="'+last.id+'"]').press('Enter');
  assert.equal(await page.locator('.analysis h2').textContent(),last.title);
  await page.locator('.contents-item[data-view="'+first.id+'"]').click();
  assert.equal(await page.locator('#question-select,#previous,#next,#counter,.navigation').count(),0);
  const layout=await page.evaluate(()=>({sidebar:document.querySelector('.sidebar').getBoundingClientRect().right,content:document.querySelector('.workspace').getBoundingClientRect().left}));
  assert(layout.sidebar<=layout.content);
  const grayStyles=await page.locator('.segment.linked').evaluateAll(nodes=>nodes.map(node=>({
   role:node.dataset.role,tone:node.dataset.tone,selected:node.classList.contains('selected'),
   color:getComputedStyle(node).backgroundColor,outline:getComputedStyle(node).outlineWidth,
   outlineStyle:getComputedStyle(node).outlineStyle,shadow:getComputedStyle(node).boxShadow
  })));
  assert(grayStyles.every(item=>item.tone===(item.role==='interviewer'?'dark':'light')));
  assert(grayStyles.every(item=>item.color===(item.selected
   ?(item.tone==='dark'?'rgb(208, 208, 208)':'rgb(231, 231, 231)')
   :(item.tone==='dark'?'rgb(229, 229, 229)':'rgb(244, 244, 244)'))));
  assert(grayStyles.filter(item=>item.selected).every(item=>parseFloat(item.outline)>=2&&item.outlineStyle==='solid'&&item.shadow!=='none'));
  await page.screenshot({path:path.join(artifacts,'desktop.png')});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.waitForFunction(()=>!document.getElementById('contents').open);
  await page.locator('#contents>summary').click();
  await page.locator('.contents-item[data-view="'+last.id+'"]').click();
  assert.equal(await page.locator('.analysis h2').textContent(),last.title);
  assert.equal(await page.locator('#contents').getAttribute('open'),null);
  await page.screenshot({path:path.join(artifacts,'mobile.png')});
  await page.locator('#contents>summary').click();
  await page.screenshot({path:path.join(artifacts,'mobile-contents.png')});
  await page.setViewportSize({width:1024,height:768});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);
  const result={mode:options.full?'full':'smoke',question_count:questions.length,checked_questions:indices.length,
   recommendations_expanded:true,source_segments:source.length,source_preserved:true,interactions:true,
   sidebar:true,mobile:true,browser_seconds:+((performance.now()-started)/1000).toFixed(3),errors};
  fs.writeFileSync(path.join(artifacts,'浏览器校验.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
