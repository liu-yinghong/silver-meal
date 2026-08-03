class InvalidOrderTransition(Exception):
    """订单状态机拒绝非法转换（如未送达即确认、已送达后取消）。"""

    def __init__(self, message: str = '订单状态不允许该操作'):
        self.message = message
        super().__init__(message)
