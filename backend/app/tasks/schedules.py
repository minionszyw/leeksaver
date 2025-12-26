"""
自定义 Celery Schedule 类

支持 offset 的固定间隔调度，用于 L2 任务错开执行。
"""

from datetime import datetime, timedelta

from celery.schedules import schedule


class OffsetSchedule(schedule):
    """
    支持 offset 的固定间隔调度

    Args:
        run_every: 执行间隔（timedelta）
        offset: 首次执行延迟（timedelta）

    Example:
        # 每 300 秒执行一次，但首次执行延迟 120 秒
        OffsetSchedule(
            run_every=timedelta(seconds=300),
            offset=timedelta(seconds=120),
        )
    """

    def __init__(self, run_every, offset=None, **kwargs):
        super().__init__(run_every, **kwargs)
        self.offset = offset or timedelta(seconds=0)
        self._has_run_once = False

    def remaining_estimate(self, last_run_at):
        """
        计算距离下次执行的剩余时间

        首次执行考虑 offset，后续执行使用正常间隔。
        """
        if not self._has_run_once:
            # 首次执行：考虑 offset
            return self.offset
        else:
            # 后续执行：正常间隔
            return super().remaining_estimate(last_run_at)

    def is_due(self, last_run_at):
        """
        判断是否应该执行

        Returns:
            (is_due, next_time_to_run): 是否应该执行，以及下次执行的时间（秒）
        """
        rem_delta = self.remaining_estimate(last_run_at)
        remaining = max(rem_delta.total_seconds(), 0)

        if remaining == 0:
            self._has_run_once = True
            return True, self.run_every.total_seconds()

        return False, remaining
