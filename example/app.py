from sanic import Sanic, response
import html5_parser

app = Sanic(name="prefab-example")


@app.post("/")
async def html_to_text(request):
    tree = html5_parser.parse(request.body)
    return response.text(tree.xpath("normalize-space(//*)"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
