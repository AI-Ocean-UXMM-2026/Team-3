const {defineConfig}=require('@playwright/test');
module.exports=defineConfig({
  testDir:'./tests/browser', timeout:90000, expect:{timeout:12000},
  fullyParallel:false, workers:1, retries:0,
  reporter:[['list'],['json',{outputFile:'test-results/browser-results.json'}]],
  use:{browserName:'chromium',headless:true,actionTimeout:12000,viewport:{width:1440,height:900},
    locale:'en-US',timezoneId:'Asia/Rangoon',trace:'off',video:'off'},
});
