from screeninfo import get_monitors
def get_principal_monitor() -> tuple:
    """
    A função retorna a dimensão da tela principal.
    Retorna: (largura, altura)
    """
    monitors = get_monitors()
    for monitor in monitors:
        if monitor.is_primary:
            return (monitor.width, monitor.height)