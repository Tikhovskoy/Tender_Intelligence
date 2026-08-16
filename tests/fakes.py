class FakeDatabase:
    """Управляемая заглушка подключения к БД."""

    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.connected = False

    async def connect(self) -> bool:
        self.connected = True
        return self.ready

    async def is_ready(self) -> bool:
        return self.connected and self.ready

    async def disconnect(self) -> None:
        self.connected = False
