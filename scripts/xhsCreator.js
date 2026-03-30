const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const userDataDir = path.join(__dirname, '.pw-user-data');
  const uploadFilePath = path.join(__dirname, 'upload.png');
  const postActionWaitMs = 10000;

  let context;
  try {
    // 持久化上下文可复用登录态
    context = await chromium.launchPersistentContext(userDataDir, {
      headless: false
    });

    const page = await context.newPage();
    await page.goto('https://creator.xiaohongshu.com/publish/publish?from=tab_switch&target=image');

    // 上传按钮通常触发 filechooser，不能直接对 button 调用 setInputFiles
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      page.getByRole('button', { name: '上传图片' }).click()
    ]);
    await fileChooser.setFiles(uploadFilePath);

    console.log(`上传动作完成，停留 ${postActionWaitMs / 1000} 秒用于观察效果...`);
    await page.waitForTimeout(postActionWaitMs);
  } catch (err) {
    console.error('脚本执行失败:', err);
    process.exitCode = 1;
  } finally {
    if (context) {
      await context.close();
    }
  }
})();