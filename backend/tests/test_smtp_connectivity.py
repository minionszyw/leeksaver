
import asyncio
from app.config import settings
from app.utils.alert_service import alert_service

async def test_email():
    print(f"--- SMTP 状态诊断 ---")
    print(f"SMTP Enabled: {settings.smtp_enabled}")
    print(f"SMTP Host: {settings.smtp_host}")
    print(f"SMTP User: {settings.smtp_user}")
    print(f"SMTP To: {settings.smtp_to}")
    
    if not settings.smtp_enabled:
        print("❌ 错误: 配置文件显示 SMTP 未启用。请检查环境变量加载情况。")
        return

    print(f"开始发送测试邮件...")
    try:
        alert_service.send_email(
            "SMTP 连通性测试", 
            "<h1>测试成功</h1><p>这是一封来自 LeekSaver 的自动测试邮件，如果您收到此邮件，说明报警系统配置正确。</p>"
        )
        print("✅ 测试任务已提交，请检查邮箱收件箱。")
    except Exception as e:
        print(f"💥 发送过程中出错: {e}")

if __name__ == "__main__":
    asyncio.run(test_email())
