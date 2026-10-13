from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from BD.job import run_once


def check() -> None:
    print(f"Проверка {datetime.now():%Y-%m-%d %H:%M}", flush=True)
    try:
        run_once()
    except SystemExit as stop:
        print(stop)
        raise
    except Exception as error:
        print(error, flush=True)


def main() -> None:
    try:
        check()
    except SystemExit:
        return
    scheduler = BlockingScheduler()
    scheduler.add_job(
        check,
        trigger="interval",
        days=1,
        id="declarations",
        max_instances=1,
        coalesce=True,
    )
    print("Следующие проверки раз в сутки.", flush=True)
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
