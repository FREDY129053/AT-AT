from .parsing.schema_parser import SchemaParser

def main():
    import logging
    logger = logging.getLogger(__name__)
    logger.info("API TESTER START")

    parser = SchemaParser("http://localhost:8000/openapi.json")
    paths = parser.get_all_paths() or []
    logger.info(f"ALL METHODS LEN = {len(paths)}")

    t = parser.get_path_schema(paths[0])
    print(t.path + "  " + t.method)
    print(t.params)
    print(t.responses)

if __name__ == "__main__":
    main()