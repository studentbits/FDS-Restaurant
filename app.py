from flask import Flask, jsonify, request
import os
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Initialize Flask app
app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI') 

try:
    # Connect to MongoDB
    client = MongoClient(MONGO_URI)
    client.admin.command('ping')  # Verify connection
    print("Database connected successfully.")
    db = client["FoodDeliveryApp"]
    users = db["user"]
    menus = db["menu"]
    orders = db["order"]
except ConnectionFailure:
    print("Failed to connect to the database.")


####### Menu API Section #################################

# Route to add menu items for a restaurant
@app.route('/menu/<restaurant_id>', methods=['POST'])
def add_menu(restaurant_id):
    # Get menu data from request
    data = request.get_json()

    # Validate the incoming data
    if not data.get('product_name') or not data.get('price') or not data.get('detail'):
        return jsonify({"msg": "Missing required fields (product_name, price, detail)"}), 400
    
    # Prepare the new product to be added
    new_menu_item = {
        "product_name": data.get('product_name'),
        "price": data.get('price'),
        "detail": data.get('detail')
    }

    try:
        # Check if the restaurant already has a menu
        existing_menu = menus.find_one({"restaurant_id": ObjectId(restaurant_id)})

        if existing_menu:
            # If menu exists, update by appending the new menu item to the existing list
            menus.update_one(
                {"restaurant_id": ObjectId(restaurant_id)}, 
                {"$push": {"menu_items": new_menu_item}}  # $push adds the item to the array
            )

            return jsonify({"msg": "Menu item added successfully to existing menu"}), 200
        else:
            # If no menu exists, create a new menu document with the restaurant_id
            new_menu = {
                "restaurant_id": ObjectId(restaurant_id),
                "menu_items": [new_menu_item]  # Create a new list with the first item
            }

            # Insert the new menu for the restaurant
            menus.insert_one(new_menu)

            return jsonify({"msg": "New menu created and item added successfully"}), 201

    except Exception as e:
        return jsonify({"msg": "Error adding menu item", "error": str(e)}), 500

# Route to get all menu items for a specific restaurant
@app.route('/menu/<restaurant_id>', methods=['GET'])
def get_menu(restaurant_id):
    try:
        # Query the menu collection to find the menu of the restaurant by restaurant_id
        restaurant_menu = menus.find_one({"restaurant_id": ObjectId(restaurant_id)})

        if restaurant_menu:
            # Convert ObjectId to string for the response
            restaurant_menu['_id'] = str(restaurant_menu['_id'])
            # Return the menu items
            return jsonify({"msg": "Menu retrieved successfully", "menu": restaurant_menu['menu_items']}), 200
        else:
            return jsonify({"msg": "No menu found for the given restaurant_id"}), 404

    except Exception as e:
        return jsonify({"msg": "Error retrieving menu", "error": str(e)}), 500

# Update menu items
@app.route('/menu/<restaurant_id>', methods=['PUT'])
def update_menu(restaurant_id):
    data = request.get_json()

    try:
        # Find the restaurant menu using restaurant_id
        restaurant_menu = menus.find_one({"restaurant_id": ObjectId(restaurant_id)})

        if not restaurant_menu:
            return jsonify({"msg": "Restaurant menu not found"}), 404

        # Check if product_name is provided in the data
        if not data.get('product_name'):
            return jsonify({"msg": "Product name is required"}), 400

        # Find the product inside the menu_items array by product_name
        existing_product = next((item for item in restaurant_menu['menu_items'] if item['product_name'] == data['product_name']), None)

        if existing_product:
            # Prepare the update object to only include fields that are provided in the data
            update_data = {}

            # Only update the fields that are present in the request data
            if 'price' in data:
                update_data["menu_items.$.price"] = data['price']
            if 'detail' in data:
                update_data["menu_items.$.detail"] = data['detail']

            # Update the menu with the provided fields
            result = menus.update_one(
                {"restaurant_id": ObjectId(restaurant_id), "menu_items.product_name": data['product_name']},
                {"$set": update_data}  # Dynamically set the fields to update
            )

            if result.modified_count > 0:
                return jsonify({"msg": "Menu item updated successfully"}), 200
            else:
                return jsonify({"msg": "No changes made to the product"}), 400
        else:
            return jsonify({"msg": "Product not found in the menu"}), 404

    except Exception as e:
        return jsonify({"msg": "Error updating menu", "error": str(e)}), 500

# Deleting a item from the menu
@app.route('/menu/<restaurant_id>/<product_name>', methods=['DELETE'])
def delete_menu_item(restaurant_id, product_name):
    try:
        # Find the restaurant menu using restaurant_id
        restaurant_menu = menus.find_one({"restaurant_id": ObjectId(restaurant_id)})

        if not restaurant_menu:
            return jsonify({"msg": "Restaurant menu not found"}), 404

        # Find the menu item by product_name
        menu_items = restaurant_menu['menu_items']
        item_to_remove = next((item for item in menu_items if item['product_name'] == product_name), None)

        if not item_to_remove:
            return jsonify({"msg": "Product not found in the menu"}), 404

        # Remove the item from the menu_items list
        result = menus.update_one(
            {"restaurant_id": ObjectId(restaurant_id)},
            {"$pull": {"menu_items": {"product_name": product_name}}}  # Use $pull to remove item by product_name
        )

        if result.modified_count > 0:
            return jsonify({"msg": "Menu item deleted successfully"}), 200
        else:
            return jsonify({"msg": "No changes made to the menu"}), 400

    except Exception as e:
        return jsonify({"msg": "Error deleting menu item", "error": str(e)}), 500

# Get  All Menu
@app.route('/menu', methods=['GET'])
def get_all_menus():
    try:
        # Retrieve all menus from the collection
        all_menus = list(menus.find({}))

        if not all_menus:
            return jsonify({"msg": "No menus found"}), 404

        # Format the response: convert ObjectId to string and include menu items
        formatted_menus = []
        for menu in all_menus:
            formatted_menus.append({
                "_id": str(menu["_id"]),
                "restaurant_id": str(menu["restaurant_id"]),
                "menu_items": menu["menu_items"]
            })

        return jsonify({"msg": "Menus retrieved successfully", "menus": formatted_menus}), 200

    except Exception as e:
        return jsonify({"msg": "Error fetching menus", "error": str(e)}), 500


############### Order Section #################################

# Add a new order
@app.route('/order/<user_id>/<restaurant_id>', methods=['POST'])
def add_order(user_id, restaurant_id):
    try:
        # Get data from request body
        data = request.get_json()

        # Validate required fields
        required_fields = ["status", "menu_detail", "total_price", "delivery_person_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"msg": f"Missing required field: {field}"}), 400

        # Prepare the order document
        order_data = {
            "user_id": ObjectId(user_id),
            "restaurant_id": ObjectId(restaurant_id),
            "status": data["status"],
            "menu_detail": data["menu_detail"],  # Assume this is a list or detailed object
            "total_price": data["total_price"],
            "delivery_person_id": ObjectId(data["delivery_person_id"])
        }

        # Insert the order into the database
        order_id = orders.insert_one(order_data).inserted_id

        # Fetch the inserted order to include all fields
        inserted_order = orders.find_one({"_id": order_id})

        # Convert ObjectId fields to strings for the response
        inserted_order["_id"] = str(inserted_order["_id"])
        inserted_order["user_id"] = str(inserted_order["user_id"])
        inserted_order["restaurant_id"] = str(inserted_order["restaurant_id"])
        inserted_order["delivery_person_id"] = str(inserted_order["delivery_person_id"])

        return jsonify({"msg": "Order added successfully", "order_data": inserted_order}), 201

    except Exception as e:
        return jsonify({"msg": "Error adding order", "error": str(e)}), 500

# Change status of order
@app.route('/order/<order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    try:
        # Get the delivery_person_id and new status from the request body
        data = request.get_json()

        # Validate the required fields
        if "delivery_person_id" not in data or "status" not in data:
            return jsonify({"msg": "Missing required fields: 'delivery_person_id' and 'status'"}), 400

        # Fetch the order by order_id
        order = orders.find_one({"_id": ObjectId(order_id)})

        if not order:
            return jsonify({"msg": "Order not found"}), 404

        # Check if the delivery person is valid for this order
        if str(order["delivery_person_id"]) != data["delivery_person_id"]:
            return jsonify({"msg": "Unauthorized: You are not assigned to this order"}), 403

        # Update the order status
        result = orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": data["status"]}}
        )

        if result.modified_count > 0:
            # Fetch the updated order to return
            updated_order = orders.find_one({"_id": ObjectId(order_id)})
            updated_order["_id"] = str(updated_order["_id"])
            updated_order["user_id"] = str(updated_order["user_id"])
            updated_order["restaurant_id"] = str(updated_order["restaurant_id"])
            updated_order["delivery_person_id"] = str(updated_order["delivery_person_id"])

            return jsonify({"msg": "Order status updated successfully", "order": updated_order}), 200
        else:
            return jsonify({"msg": "No changes made to the order"}), 400

    except Exception as e:
        return jsonify({"msg": "Error updating order status", "error": str(e)}), 500


# Start the Flask app
if __name__ == "__main__":
    print("Starting the server...")
    app.run(host="0.0.0.0", port=8083, debug=True)
