import json

def generate_bpa_catalog():
    colors = ["Black", "White", "Pink"]
    sizes = ["Small", "Medium", "Large"]
    footwear_colors = ["Brown", "Black", "White"]
    footwear_sizes = [str(i) for i in range(1, 11)]
    
    catalog = []

    # 1. Winter Coats (3 types: Hiking, Skiing, Skating)
    for style in ["Hiking", "Skiing", "Skating"]:
        for gender in ["W", "M"]:
            gender_name = "Women's" if gender == "W" else "Men's"
            # Full Expansion for Coats
            for color in colors:
                for size in sizes:
                    catalog.append({
                        "id": f"BPA-COAT-{gender}-{style[:3].upper()}-{color[:3].upper()}-{size[0]}",
                        "name": f"{gender_name} {style} Coat ({color}, {size})",
                        "description": f"High-performance {style.lower()} coat. Tailored {size} fit.",
                        "picture": f"/static/img/products/coat-{gender.lower()}-{style.lower()}.jpg",
                        "price_usd": {"currency_code": "USD", "units": 150, "nanos": 0},
                        "categories": [gender_name.lower().replace("'s", "s"), "coats", "winter"]
                    })

    # 2. Shirts (2 designs: Wayfinder, Windjammer)
    designs = {"Wayfinder": "woods scene", "Windjammer": "lake scene"}
    for design, scene in designs.items():
        for gender in ["W", "M"]:
            gender_name = "Women's" if gender == "W" else "Men's"
            for color in colors:
                for size in sizes:
                    catalog.append({
                        "id": f"BPA-SHIRT-{gender}-{design[:3].upper()}-{color[:3].upper()}-{size[0]}",
                        "name": f"{gender_name} {design} Shirt ({color}, {size})",
                        "description": f"Features a {scene}. Available in {color}.",
                        "picture": f"/static/img/products/shirt-{design.lower()}.jpg",
                        "price_usd": {"currency_code": "USD", "units": 40, "nanos": 0},
                        "categories": [gender_name.lower().replace("'s", "s"), "shirts", "apparel"]
                    })

    # 3. Footwear (2 types: Hikers Boots, Jim Shoes)
    for fw_type in [("Hikers Boots", "BOOT"), ("Jim Shoes", "SHOE")]:
        name, code = fw_type
        for gender in ["W", "M"]:
            gender_name = "Women's" if gender == "W" else "Men's"
            for color in footwear_colors:
                for size in footwear_sizes:
                    catalog.append({
                        "id": f"BPA-FW-{gender}-{code}-{color[:3].upper()}-{size}",
                        "name": f"{gender_name} {name} ({color}, Size {size})",
                        "description": f"Durable {name.lower()} for outdoor adventures.",
                        "picture": f"/static/img/products/{code.lower()}.jpg",
                        "price_usd": {"currency_code": "USD", "units": 95, "nanos": 0},
                        "categories": [gender_name.lower().replace("'s", "s"), "footwear"]
                    })

    return catalog

# Save to file
with open('bpa_products.json', 'w') as f:
    json.dump({"products": generate_bpa_catalog()}, f, indent=2)

print(f"Generated {len(generate_bpa_catalog())} product variants.")
