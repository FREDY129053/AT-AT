import asyncio
from .openapi_parser import SwaggerParser


###############################
######    TEMP DEFS       #####
###############################
def _print_colorfull_method(method_type, s):
    COLORS = {
        "reset": "\033[0m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "grey": "\033[90m",
    }
    match method_type:
        case "GET":
            color = COLORS["green"]
        case "POST":
            color = COLORS["blue"]
        case "PUT":
            color = COLORS["cyan"]
        case "DELETE":
            color = COLORS["red"]
        case "OPTIONS":
            color = COLORS["yellow"]
        case "HEAD":
            color = COLORS["magenta"]
        case "PATCH":
            color = COLORS["grey"]
        case "TRACE":
            color = COLORS["reset"]
        case _:
            color = COLORS["reset"]
    print(f"{color}{s}{COLORS['reset']}\n")


###############################
######      MAIN DEFS     #####
###############################
async def main():
    TEST_URL = "https://petstore.swagger.io/v2/swagger.json"
    TEST_URL = "https://www.socrambanque.fr/openbanking-test/v4/swagger.json"

    # Forbidden
    # TEST_URL = (
    #    "https://integration-openbanking-api.dev.fin.ag/swagger/v0.1/swagger.json"
    # )

    # TEST_URL = "https://bank.sandbox.cybrid.app/api/schema/v1/swagger.yaml"
    # TEST_URL = "https://fakerestapi.azurewebsites.net/swagger/v1/swagger.json"
    TEST_URL = "http://127.0.0.1:8000/openapi.json"

    s = SwaggerParser(TEST_URL)
    spec = await s.parse_swagger()

    # for method in spec.endpoints:
    # print(method.model_dump_json())
    with open("temp.txt", "w", encoding="utf-8") as file:
        file.writelines(
            str(method.model_dump_json()).rstrip("\n") + "\n"
            for method in spec.endpoints
        )
        # file.write(method.model_dump_json().rstrip("\n") + "\n")
        # _print_colorfull_method(
        #    method.type.value,
        #    f"{method.url} - {method.type.value}\n\tPARAMS: {method.parameters}\n\tREQUEST BODY: {method.request_body.__repr__()}\n\tRESPONSES: {method.responses}",
        # )


if __name__ == "__main__":
    asyncio.run(main())
