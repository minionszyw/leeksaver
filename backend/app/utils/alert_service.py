"""
报警通知服务

支持 SMTP 邮件通知，用于下发数据质量告警。
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytz

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class AlertService:
    """报警通知服务"""

    @staticmethod
    def _get_now_str() -> str:
        """获取带时区格式化的当前时间字符串"""
        tz = pytz.timezone(settings.timezone)
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def send_email(subject: str, html_content: str):
        """
        发送报警邮件 (同步模式，供 Celery 或脚本调用)
        """
        if not settings.smtp_enabled:
            logger.debug("SMTP 邮件报警未启用")
            return

        if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password, settings.smtp_to]):
            logger.warning("SMTP 配置不完整，无法发送报警")
            return

        try:
            # 创建邮件对象
            message = MIMEMultipart("alternative")
            message["Subject"] = f"【LeekSaver 警报】{subject}"
            message["From"] = settings.smtp_from or settings.smtp_user
            message["To"] = settings.smtp_to

            # 添加 HTML 内容
            part = MIMEText(html_content, "html")
            message.attach(part)

            # 连接服务器并发送
            if settings.smtp_tls:
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(message["From"], [message["To"]], message.as_string())
            server.quit()
            
            logger.info(f"📧 报警邮件已发送: {subject}")
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")

    @classmethod
    def send_dqa_report(cls, results: list, stubborn_codes: set = None):
        """
        基于 DQA 巡检结果发送结构化报告邮件
        
        优化策略：仅在需要“人工干预”时骚扰管理员。
        1. 存在“顽疾”标的 (stubborn_codes) -> 必须报。
        2. 系统新鲜度异常 (freshness critical) -> 说明同步链路断了，必须报。
        3. 覆盖率出现严重空洞 (CRITICAL) -> 意味着自动修复可能赶不上损耗，必须报。
        4. 普通 WARNING 覆盖率或逻辑错误 -> 系统会自动下发自愈任务，保持静默。
        """
        has_stubborn = stubborn_codes and len(stubborn_codes) > 0
        has_system_failure = any(r.metric_name == "freshness" and r.status == "critical" for r in results)
        has_critical_void = any(r.metric_name.endswith("_coverage") and r.status == "critical" for r in results)
        
        if not (has_stubborn or has_system_failure or has_critical_void):
            logger.info("ℹ️ 巡检异常已由自愈系统接管，无需发送告警邮件。")
            return

        now = cls._get_now_str()
        
        # 构建 HTML 表格
        rows = ""
        for r in results:
            color = "#ff4d4f" if r.status == "critical" else ("#faad14" if r.status == "warning" else "#52c41a")
            rows += f"""
            <tr style="border-bottom: 1px solid #f0f0f0;">
                <td style="padding: 12px; color: #666;">{r.metric_name}</td>
                <td style="padding: 12px; color: {color}; font-weight: bold;">{r.status.upper()}</td>
                <td style="padding: 12px;">{r.message}</td>
            </tr>
            """

        stubborn_section = ""
        if has_stubborn:
            codes_str = ", ".join(list(stubborn_codes)[:20])
            if len(stubborn_codes) > 20: codes_str += "..."
            stubborn_section = f"""
            <div style="margin-top: 20px; padding: 15px; background: #fff2f0; border: 1px solid #ffccc7; border-radius: 4px;">
                <h3 style="color: #ff4d4f; margin-top: 0;">🚫 熔断警告：发现顽疾标的 ({len(stubborn_codes)}只)</h3>
                <p style="color: #666; font-size: 14px;">以下标的多次自愈修复失败，已触发熔断保护，请人工检查上游接口或网络：</p>
                <code style="background: #fff; padding: 5px; display: block;">{codes_str}</code>
            </div>
            """

        html = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; background: #f9f9f9; padding: 20px;">
            <div style="max-width: 800px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                <h2 style="color: #1a1a1a; border-bottom: 2px solid #eee; padding-bottom: 10px;">LeekSaver 数据质量巡检报告 (Ultra)</h2>
                <p style="color: #999; font-size: 12px;">巡检时间: {now}</p>
                
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <thead>
                        <tr style="background: #fafafa; text-align: left; border-bottom: 2px solid #f0f0f0;">
                            <th style="padding: 12px;">监控维度</th>
                            <th style="padding: 12px;">状态</th>
                            <th style="padding: 12px;">诊断信息</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>

                {stubborn_section}

                <div style="margin-top: 30px; font-size: 12px; color: #aaa; text-align: center; border-top: 1px solid #eee; padding-top: 20px;">
                    本邮件由 LeekSaver Data Doctor 自动发出，请勿直接回复。
                </div>
            </div>
        </body>
        </html>
        """
        
        cls.send_email(f"数据异常报告 ({now})", html)

# 全局单例
alert_service = AlertService()
