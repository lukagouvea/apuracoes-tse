const fs=require('fs');
const path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',args:['--no-sandbox','--disable-gpu','--disable-software-rasterizer','--renderer-process-limit=1','--num-raster-threads=1']});
 const page=await browser.newPage({viewport:{width:1440,height:1150},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('file://'+path.resolve('reports/apuracao.html'));
 await page.waitForSelector('#chart path');
 if(await page.locator('#chart path').count()!==2)throw Error('Expected two candidate series');
 await page.screenshot({path:'reports/previews/apuracao-desktop.png',fullPage:true});
 const years=await page.locator('.year').evaluateAll(es=>es.map(e=>Number(e.dataset.year)));
 if(JSON.stringify(years)!==JSON.stringify([2018,2022,2026]))throw Error('Only study years should be selectable: '+years);
 if(!(await page.locator('.all-years').textContent()).includes('primeiro turno do mesmo ano'))throw Error('Incorrect first-turn reference description');
 for(const year of [2022,2018,2026,2018,2026]){
   await page.locator('.year[data-year="'+year+'"]').click();
   if(!(await page.locator('#axis-label').textContent()).includes('%'))throw Error('Fixed percentage axis label missing for '+year);
   if(await page.locator('#axis-time').count())throw Error('Time axis control must not be offered');
     if(await page.locator('#chart path').count()!==2)throw Error('Candidate curves missing for '+year);
     const labels=await page.locator('#chart text').allTextContents();
     if(!labels.includes('100%')||labels.some(t=>/\d{2}:\d{2}/.test(t)))throw Error('Horizontal axis changed away from percent for '+year);
     if((await page.locator('#chart').innerHTML()).includes('NaN'))throw Error('Invalid chart coordinates for '+year);
 }
 await page.reload();await page.waitForSelector('#chart path');
 if(!await page.locator('.year[data-year="2026"]').getAttribute('aria-current'))throw Error('Default year missing after reload');
 if(!(await page.locator('#chart text').allTextContents()).includes('100%'))throw Error('Reload lost percentage axis');
 await page.locator('#update-slider').evaluate(e=>{e.value=0;e.dispatchEvent(new Event('input',{bubbles:true}));});
 if(!(await page.locator('#point-label').textContent()).includes('25/10'))throw Error('Update slider failed');
 await page.locator('.year[data-year="2022"]').click();
 const download=page.waitForEvent('download');await page.locator('#export-csv').click();
 const file=await download;if(!file.suggestedFilename().includes('2022'))throw Error('CSV export failed');
 await file.saveAs('reports/previews/apuracao-2022.csv');
 await page.locator('.year[data-year="2018"]').click();
 await page.locator('#update-slider').evaluate(e=>{e.value=e.max;e.dispatchEvent(new Event('input',{bubbles:true}));});
 if(!(await page.locator('#point-label').textContent()).includes('25/02'))throw Error('Late records were lost on the percent axis');
 await page.setViewportSize({width:390,height:844});
 await page.locator('.year[data-year="2026"]').click();
 await page.screenshot({path:'reports/previews/apuracao-mobile.png',fullPage:true});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth))throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error(errors.join('\n'));
 console.log('HTML: only 2018/2022/2026, fixed percentage axis across reload/year changes, slider, CSV, late records and mobile passed.');
 if(process.argv.includes('--html-only')){await browser.close();return;}
 const graphs=[];
 for(const file of ['docs/especificacao.md','docs/dados.md','docs/metodologia.md']){
   const text=fs.readFileSync(file,'utf8');for(const m of text.matchAll(/```mermaid\n([\s\S]*?)```/g))graphs.push({file,code:m[1]});
 }
 await page.setViewportSize({width:1200,height:1000});
 await page.goto('http://127.0.0.1:8779/');
 await page.setContent('<html><head></head><body style="margin:30px;font-family:system-ui"><h1>Diagramas da especificação</h1><div id="graphs"></div></body></html>');
 await page.addScriptTag({type:'module',content:"import mermaid from '/mermaid/dist/mermaid.esm.min.mjs'; window.mermaid=mermaid; mermaid.initialize({startOnLoad:false,theme:'default'});"});
 await page.waitForFunction(()=>!!window.mermaid);
 const rendered=await page.evaluate(async graphs=>{
   for(let i=0;i<graphs.length;i++){
     await window.mermaid.parse(graphs[i].code);
     const {svg}=await window.mermaid.render('diagram-'+i,graphs[i].code);
     const div=document.createElement('section');div.style='border-bottom:1px solid #ddd;padding:20px 0';div.innerHTML='<h2>'+graphs[i].file+' · '+(i+1)+'</h2>'+svg;document.querySelector('#graphs').appendChild(div);
   }
   return graphs.length;
 },graphs);
 await page.screenshot({path:'reports/previews/diagramas.png',fullPage:true});
 console.log('Mermaid: '+rendered+' diagrams parsed and rendered.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
