"""Пример: путь к chromedriver, затем название, на экран — только ссылки."""

from domrf import ProjectDeclarations


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def main() -> None:
    driver_path = ask("Путь к chromedriver: ")
    if not driver_path:
        return
    try:
        catalog = ProjectDeclarations(driver_path)
    except Exception as error:
        print(error)
        return
    try:
        while True:
            name = ask("Название: ")
            if not name:
                break
            try:
                urls = catalog.links(name)
            except Exception as error:
                print(error)
                print()
                continue
            if not urls:
                print("Ссылок нет.")
            for url in urls:
                print(url)
            print()
    finally:
        catalog.close()


if __name__ == "__main__":
    main()
