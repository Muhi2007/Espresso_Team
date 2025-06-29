# style_ai
def get_suggestions(category, style):
    suggestions = {
        ("t-shirt", "streetwear"): ["Baggy Jeans", "Sneakers", "Bucket Hat"],
    }
    return suggestions.get((category, style), ["Couldn't find the fitting style"])