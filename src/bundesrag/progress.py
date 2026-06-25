from bundesrag.i18n import t


def step(n: int, total: int, name: str) -> None:
    print(t("progress_step", n=n, total=total, name=name))
