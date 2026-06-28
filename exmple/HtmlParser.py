from bs4 import BeautifulSoup

html = """
<html>
    <body>
        <h1>Products</h1>
        <div class="product">
            <h2>iPhone 16</h2>
            <span class="price">$999</span>
        </div>
        <div class="product">
            <h2>Samsung S26</h2>
            <span class="price">$899</span>
        </div>
    </body>
</html>
"""

soup = BeautifulSoup(html, "html.parser")

products = soup.find_all("div", class_="product")

for product in products:
    name = product.find("h2").text
    price = product.find("span", class_="price").text
    print(f"Product: {name}, Price: {price}")