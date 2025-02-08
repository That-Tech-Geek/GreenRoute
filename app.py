import streamlit as st
st.set_page_config(
    page_title="GreenRoute - Sustainable Logistics Dashboard",
    page_icon="🌱",
    layout="wide",
)

import pandas as pd
import numpy as np
import altair as alt
import requests
from datetime import datetime
from supabase import create_client, Client
import cohere  # For generating advice
import folium
from streamlit_folium import st_folium

# ============================
# API KEYS and CONFIGURATION
# ============================
API_KEYS = st.secrets.get("NEWS-API", {})
NEWS_API_KEY = API_KEYS.get("NEWS_API", "YOUR_NEWS_API_KEY")  # using key NEWS_API from the NEWS-API section
COHERE_API_KEY = API_KEYS.get("COHERE_API_KEY", "YOUR_COHERE_API_KEY")

SUPABASE_CONFIG = st.secrets.get("supabase", {})
SUPABASE_URL = SUPABASE_CONFIG.get("url", "YOUR_SUPABASE_PROJECT_URL")
SUPABASE_ANON_KEY = SUPABASE_CONFIG.get("anon_key", "YOUR_SUPABASE_ANON_KEY")
SUPABASE_TABLE = SUPABASE_CONFIG.get("table_name", "feedback")
# For sustainability metrics, we are now using Sheety (see below)

# ============================
# Sheety Metrics Functions
# ============================
SHEETY_CONFIG = st.secrets.get("sheety", {})
SHEETY_METRICS_URL = SHEETY_CONFIG.get("metrics_url", "YOUR_SHEETY_METRICS_URL")

@st.cache_data
def get_metrics_from_sheety():
    """
    Retrieve the current sustainability metrics from the Sheety API.
    Expects the API to return JSON with a key "metrics" that is a list.
    """
    response = requests.get(SHEETY_METRICS_URL)
    if response.status_code == 200:
        data = response.json()
        if "metrics" in data and len(data["metrics"]) > 0:
            return data["metrics"][0]
        else:
            return {"routes_simulated": 0, "total_emissions_saved": 0, "fuel_savings": 0}
    else:
        st.error("Error fetching metrics from Sheety: " + str(response.status_code))
        return {"routes_simulated": 0, "total_emissions_saved": 0, "fuel_savings": 0}

def update_metrics_in_sheety(new_routes: int, new_emissions: float):
    """
    Update the sustainability metrics in Sheety by adding new data.
    If no metrics exist, create a new row; otherwise, update the existing row.
    Clears the cache after updating.
    """
    fuel_saving_per_route = 50   # e.g., each route saves 50 liters
    current_metrics = get_metrics_from_sheety()
    
    if (current_metrics.get("routes_simulated", 0) == 0 and 
        current_metrics.get("total_emissions_saved", 0) == 0 and 
        current_metrics.get("fuel_savings", 0) == 0):
        new_metrics = {
            "routes_simulated": new_routes,
            "total_emissions_saved": new_emissions,
            "fuel_savings": new_routes * fuel_saving_per_route
        }
        response = requests.post(SHEETY_METRICS_URL, json={"metrics": new_metrics})
        if response.status_code not in [200, 201]:
            st.error("Error inserting new metrics: " + response.text)
    else:
        updated = {
            "routes_simulated": current_metrics.get("routes_simulated", 0) + new_routes,
            "total_emissions_saved": current_metrics.get("total_emissions_saved", 0) + new_emissions,
            "fuel_savings": current_metrics.get("fuel_savings", 0) + new_routes * fuel_saving_per_route
        }
        row_id = current_metrics.get("id")
        if row_id:
            update_url = SHEETY_METRICS_URL + f"/{row_id}"
            response = requests.put(update_url, json={"metrics": updated})
            if response.status_code not in [200, 201]:
                st.error("Error updating metrics: " + response.text)
        else:
            st.error("No row id found for metrics update.")
    get_metrics_from_sheety.clear()

# ============================
# Cohere Advice Function
# ============================
def get_cohere_advice(goal: str) -> str:
    """
    Generate actionable sustainability advice using Cohere API based on the user's sustainability goal.
    """
    co = cohere.Client(COHERE_API_KEY)
    prompt = f"Provide practical, actionable advice on how to improve sustainability and reduce emissions with a focus on {goal}."
    response = co.generate(
         model="command-xlarge-nightly",
         prompt=prompt,
         max_tokens=60,
         temperature=0.7,
         k=0,
         p=0.75,
         frequency_penalty=0,
         presence_penalty=0,
         stop_sequences=["--"]
    )
    advice = response.generations[0].text.strip()
    return advice

# ============================
# API Integration Functions
# ============================
def get_coordinates(address):
    """Geocode an address using the free Nominatim API."""
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    if response.status_code == 200:
        data = response.json()
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            return lat, lon
    return None, None

def get_route_info(origin_coords, destination_coords):
    """
    Retrieve route info using OSRM API.
    Returns distance (miles), duration (hours), and route geometry as a GeoJSON LineString.
    """
    start_lon, start_lat = origin_coords[1], origin_coords[0]
    end_lon, end_lat = destination_coords[1], destination_coords[0]
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
        f"?overview=full&geometries=geojson"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data and "routes" in data and len(data["routes"]) > 0:
            route = data["routes"][0]
            distance = route["distance"] / 1609.34  # convert meters to miles
            duration = route["duration"] / 3600.0     # convert seconds to hours
            geometry = route.get("geometry", {}).get("coordinates", [])
            # Fallback: if geometry is empty, use a straight-line path
            if not geometry:
                geometry = [[start_lon, start_lat], [end_lon, end_lat]]
            return distance, duration, geometry
    return None, None, None

def get_carbon_estimate(distance, vehicle_type='car'):
    """
    Estimate CO₂ emissions for a given distance (miles).
    Example: a typical car emits ~0.411 kg CO₂ per mile.
    """
    return distance * 0.411

def get_news_articles(query):
    """Fetch news articles using NewsAPI."""
    if not NEWS_API_KEY or NEWS_API_KEY == "YOUR_NEWS_API_KEY":
        return []  # No API key provided, so no live news
    url = (
        f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt"
        f"&apiKey={NEWS_API_KEY}&language=en&pageSize=5"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        articles = data.get("articles", [])
        return articles
    return []

def save_feedback_to_supabase(name, email, feedback):
    """Save user feedback to Supabase."""
    data = {
        "Name": name,
        "Email": email,
        "Feedback": feedback,
        "Timestamp": datetime.now().isoformat()
    }
    response = supabase.table(SUPABASE_TABLE).insert(data).execute()
    return response.data is not None

# ============================
# Page Configuration & Sidebar
# ============================
st.sidebar.title("Navigation")
pages = [
    "Overview", 
    "Personalized Recommendations", 
    "Educational Content",
    "Sustainability Metrics",
    "Route Optimization Simulator",
    "Real-Time News",
    "User Feedback"
]
page = st.sidebar.radio("Go to", pages)

# ============================
# Overview Page
# ============================
if page == "Overview":
    st.title("GreenRoute: Revolutionizing Sustainable Logistics")
    st.markdown("""
    **Welcome to GreenRoute!**

    Our platform leverages advanced AI, real-time data, and cutting-edge route optimization to help you make sustainable logistics decisions.
    Explore personalized recommendations, educational content, and an interactive route planner—all designed for today's logistics challenges.
    """)
    st.image("https://images.unsplash.com/photo-1504384308090-c894fdcc538d",
             caption="Sustainable Logistics in Action", use_column_width=True)
    st.markdown("### Use the sidebar to explore the features!")

# ============================
# Personalized Recommendations Page
# ============================
elif page == "Personalized Recommendations":
    st.title("Personalized Recommendations")
    st.markdown("""
    **Tailored Solutions for Your Sustainability Goals**

    Enter your sustainability focus (e.g., reducing fuel consumption, minimizing emissions) to get customized recommendations powered by our AI engine.
    """)
    user_goal = st.text_input("Enter your sustainability goal:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Get Recommendation"):
            if user_goal.strip():
                st.success(f"Based on your goal to **{user_goal.strip()}**, explore our tools designed to optimize operations and reduce environmental impact.")
            else:
                st.warning("Please enter a sustainability goal.")
    with col2:
        if st.button("Get Advice"):
            if user_goal.strip():
                advice = get_cohere_advice(user_goal.strip())
                st.markdown("### Advice:")
                st.info(advice)
            else:
                st.warning("Please enter a sustainability goal.")

# ============================
# Educational Content Page
# ============================
elif page == "Educational Content":
    st.title("Educational Content")
    st.markdown("""
    ### Dive into Sustainable Logistics

    **Sustainable Logistics:**  
    Embrace strategies that minimize environmental impact while optimizing your supply chain. Our resources cover renewable energy, electric vehicles, smart routing, and more.

    **Emissions Management:**  
    Understand best practices for tracking and reducing emissions through advanced data analytics and cleaner technologies.

    **Our Approach:**  
    - **Personalized Insights:** Custom recommendations to match your goals.
    - **Real-Time Data:** Stay ahead with live news and analytics.
    - **Interactive Tools:** Engage with dynamic simulations and educational resources.
    """)
    st.info("Empower your logistics operations with knowledge and innovation.")

# ============================
# Sustainability Metrics Page
# ============================
elif page == "Sustainability Metrics":
    st.title("Sustainability Metrics")
    st.markdown("### Overall Impact of GreenRoute")
    
    # Retrieve persistent metrics from Sheety (cached)
    metrics = get_metrics_from_sheety()
    routes_simulated = metrics.get("routes_simulated", 0)
    total_emissions_saved = metrics.get("total_emissions_saved", 0)
    fuel_savings = metrics.get("fuel_savings", 0)
    
    avg_emissions_saved = total_emissions_saved / routes_simulated if routes_simulated else 0

    st.write(f"**Total Routes Simulated:** {routes_simulated}")
    st.write(f"**Total CO₂ Emissions Saved:** {total_emissions_saved:.2f} kg")
    st.write(f"**Average Emissions Saved per Route:** {avg_emissions_saved:.2f} kg")
    st.write(f"**Estimated Fuel Savings:** {fuel_savings} liters")
    
    # Visual summary using an Altair bar chart
    metrics_df = pd.DataFrame({
        "Metric": [
            "Total Routes",
            "Total Emissions Saved (kg)",
            "Avg Emissions per Route (kg)",
            "Fuel Savings (liters)"
        ],
        "Value": [
            routes_simulated,
            total_emissions_saved,
            avg_emissions_saved,
            fuel_savings
        ]
    })
    chart = alt.Chart(metrics_df).mark_bar().encode(
        x=alt.X("Metric:N", sort=None),
        y=alt.Y("Value:Q"),
        color=alt.Color("Metric:N")
    ).properties(width=700, height=400)
    st.altair_chart(chart, use_container_width=True)
    
    st.info("GreenRoute has been instrumental in optimizing routes and reducing emissions, leading to significant environmental and economic benefits.")

# ============================
# Route Optimization Simulator Page
# ============================
elif page == "Route Optimization Simulator":
    st.title("Route Optimization Simulator")
    st.markdown("""
    **Simulate Your Route and Visualize the Optimal Path**

    Enter your origin and destination below to calculate the best route. Our system retrieves the route geometry via the OSRM API and displays it on an interactive map.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("Enter Origin", "New York, NY")
    with col2:
        destination = st.text_input("Enter Destination", "Los Angeles, CA")
    
    if st.button("Simulate Route"):
        if origin and destination:
            # Retrieve coordinates using Nominatim API (returns (lat, lon))
            origin_coords = get_coordinates(origin)
            destination_coords = get_coordinates(destination)
            if None in origin_coords or None in destination_coords:
                st.error("Could not geocode the provided addresses. Please try different inputs.")
            else:
                # Retrieve route information from OSRM API
                result = get_route_info(origin_coords, destination_coords)
                if result[0] is not None:
                    distance, duration, geometry = result
                    emissions_estimated = get_carbon_estimate(distance)
                    st.success(f"Optimized route from **{origin}** to **{destination}**:")
                    st.write(f"**Estimated Distance:** {distance:.2f} miles")
                    st.write(f"**Estimated Travel Time:** {duration:.2f} hours")
                    st.write(f"**Estimated CO₂ Emissions Saved:** {emissions_estimated:.2f} kg")
                    
                    # If OSRM does not return valid geometry, use a straight-line fallback
                    if not geometry or len(geometry) < 2:
                        # OSRM returns [lon, lat] order; fallback with a straight line
                        geometry = [[origin_coords[1], origin_coords[0]], [destination_coords[1], destination_coords[0]]]
                    
                    # Convert geometry from [lon, lat] to [lat, lon] for Folium
                    folium_geometry = [[pt[1], pt[0]] for pt in geometry]
                    
                    # Calculate the map center based on the converted geometry
                    center_lat = sum(pt[0] for pt in folium_geometry) / len(folium_geometry)
                    center_lon = sum(pt[1] for pt in folium_geometry) / len(folium_geometry)
                    
                    # Create a Folium map centered at the calculated coordinates
                    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
                    
                    # Add the route as a polyline to the map
                    folium.PolyLine(locations=folium_geometry, color="red", weight=5).add_to(m)
                    
                    # Add markers for the origin and destination
                    folium.Marker(location=[origin_coords[0], origin_coords[1]], popup="Origin").add_to(m)
                    folium.Marker(location=[destination_coords[0], destination_coords[1]], popup="Destination").add_to(m)
                    
                    # Render the Folium map using st_folium with a fixed key to help preserve state
                    from streamlit_folium import st_folium
                    st_folium(m, width=700, height=500, key="map")
                    
                    st.info("The map above shows the optimized route along with markers for the origin and destination.")
                else:
                    st.error("Could not retrieve route information. Please try again later.")
        else:
            st.warning("Please enter both origin and destination.")

# ============================
# Real-Time News Page
# ============================
elif page == "Real-Time News":
    st.title("Real-Time News")
    st.markdown("""
    **Stay Updated with the Latest in Sustainable Logistics**

    We fetch live news articles using NewsAPI to keep you informed about trends and innovations in the logistics industry.
    """)
    query = "sustainable logistics"
    articles = get_news_articles(query)
    if articles:
        for article in articles:
            st.subheader(article.get("title", "No Title"))
            st.write(article.get("description", "No Description"))
            st.markdown(f"[Read more]({article.get('url', '#')})")
            st.markdown("---")
    else:
        st.info("No real-time news available. Please ensure you have set your News API key correctly.")

# ============================
# User Feedback Page
# ============================
elif page == "User Feedback":
    st.title("User Feedback")
    st.markdown("""
    **We Value Your Input**

    Please share your feedback or suggestions to help us improve GreenRoute.
    """)
    with st.form("feedback_form"):
        name = st.text_input("Your Name")
        email = st.text_input("Your Email")
        feedback = st.text_area("Your Feedback", "Enter your feedback here...")
        submitted = st.form_submit_button("Submit Feedback")
        if submitted:
            if name and email and feedback:
                success = save_feedback_to_supabase(name, email, feedback)
                if success:
                    st.success("Thank you for your feedback! It has been successfully saved.")
                else:
                    st.error("There was an error saving your feedback. Please try again later.")
            else:
                st.warning("Please fill in all fields before submitting.")
