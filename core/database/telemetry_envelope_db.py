
from .base import session_scope, BaseDatabase
from .models import TelemetryEnvelope


class TelemetryEnvelopeDB(BaseDatabase):
    
    def save_telemetry_envelope(self, envelope_data: TelemetryEnvelope):
        """
        保存 GIT AI 收集的数据
        """
        with session_scope(self.engine) as session:
            session.add(envelope_data)
            session.flush()