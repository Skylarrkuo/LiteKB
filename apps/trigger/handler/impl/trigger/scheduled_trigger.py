"""Compatibility for legacy schedule records and trigger cleanup on upgraded databases."""
from trigger.handler.base_trigger import BaseTrigger


class ScheduledTrigger(BaseTrigger):
    @staticmethod
    def execute(trigger, **kwargs):
        return None

    def support(self, trigger, **kwargs):
        return trigger.get("trigger_type") == "SCHEDULED"

    def deploy(self, trigger, **kwargs):
        return None

    def undeploy(self, trigger, **kwargs):
        return None
