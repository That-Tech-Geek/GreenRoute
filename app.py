import streamlit as st
st.set_page_config(
    page_title="GreenRoute - Sustainable Logistics Dashboard",
    page_icon="🌱",
    layout="wide",
)

import pandas as pd
import numpy as np
import altair as alt
import pydeck as pdk
import requests
from datetime import datetime
from supabase import create_client, Client
import cohere  # Import Cohere for generating advice

# ============================
# API KEYS and CONFIGURATION
# ============================
API_KEYS = st.secrets.get("NEWS-API", {})
NEWS_API_KEY = API_KEYS.get("NEWS_API", "YOUR_NEWS_API_KEY")  # Note: using key NEWS_API from the NEWS-API section
COHERE_API_KEY = API_KEYS.get("COHERE_API_KEY", "YOUR_COHERE_API_KEY")

SUPABASE_CONFIG = st.secrets.get("supabase", {})
SUPABASE_URL = SUPABASE_CONFIG.get("url", "YOUR_SUPABASE_PROJECT_URL")
SUPABASE_ANON_KEY = SUPABASE_CONFIG.get("anon_key", "YOUR_SUPABASE_ANON_KEY")
SUPABASE_TABLE = SUPABASE_CONFIG.get("table_name", "feedback")
# Table for sustainability metrics will now use the key 'impact_table'
IMPACT_TABLE = st.secrets.get("supabase", {}).get("impact_table", "Impact")

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ============================
# Persistent Metrics Functions with Caching
# ============================
@st.cache_data
def get_metrics_from_db():
    """
    Retrieve the current sustainability metrics from Supabase.
    This result is cached to avoid repeated database queries within a session.
    """
    res = supabase.table(IMPACT_TABLE).select("*").execute()
    data = res.data
    if data:
        return data[0]
    else:
        return {
            "routes_simulated": 0,
            "total_emissions_saved": 0,
            "fuel_savings": 0,
            "cost_savings": 0
        }

def update_metrics_in_db(new_routes: int, new_emissions: float):
    """
    Update the sustainability metrics in Supabase by adding new data.
    After updating the DB, clear the cache so that subsequent calls fetch the latest data.
    Debug information is printed to help verify the update.
    """
    fuel_saving_per_route = 50   # e.g., each route saves 50 liters
    cost_saving_per_route = 100    # e.g., each route saves $100

    # Fetch the current metrics
    res = supabase.table(IMPACT_TABLE).select("*").execute()
    data = res.data
    st.write("DEBUG: Current Impact table data:", data)  # Debug output

    if not data:
        new_metrics = {
            "routes_simulated": new_routes,
            "total_emissions_saved": new_emissions,
            "fuel_savings": new_routes * fuel_saving_per_route,
            "cost_savings": new_routes * cost_saving_per_route
        }
        try:
            response = supabase.table(IMPACT_TABLE).insert(new_metrics).execute()
            st.write("DEBUG: Insert response:", response.data)  # Debug output
        except Exception as e:
            st.error("Error inserting new metrics: " + str(e))
    else:
        current = data[0]
        updated = {
            "routes_simulated": current.get("routes_simulated", 0) + new_routes,
            "total_emissions_saved": current.get("total_emissions_saved", 0) + new_emissions,
            "fuel_savings": current.get("fuel_savings", 0) + new_routes * fuel_saving_per_route,
            "cost_savings": current.get("cost_savings", 0) + new_routes * cost_saving_per_route,
        }
        record_id = current["id"]
        try:
            response = supabase.table(IMPACT_TABLE).update(updated).eq("id", record_id).execute()
            st.write("DEBUG: Update response:", response.data)  # Debug output
        except Exception as e:
            st.error("Error updating metrics: " + str(e))
    
    # Clear the cached metrics data so that subsequent calls fetch fresh data
    get_metrics_from_db.clear()

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
        if data and 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]
            distance = route['distance'] / 1609.34  # meters to miles
            duration = route['duration'] / 3600.0     # seconds to hours
            geometry = route.get("geometry", {}).get("coordinates", [])
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
    
    # Retrieve persistent metrics from Supabase (cached)
    metrics = get_metrics_from_db()
    routes_simulated = metrics.get("routes_simulated", 0)
    total_emissions_saved = metrics.get("total_emissions_saved", 0)
    fuel_savings = metrics.get("fuel_savings", 0)
    cost_savings = metrics.get("cost_savings", 0)
    
    avg_emissions_saved = total_emissions_saved / routes_simulated if routes_simulated else 0

    st.write(f"**Total Routes Simulated:** {routes_simulated}")
    st.write(f"**Total CO₂ Emissions Saved:** {total_emissions_saved:.2f} kg")
    st.write(f"**Average Emissions Saved per Route:** {avg_emissions_saved:.2f} kg")
    st.write(f"**Estimated Fuel Savings:** {fuel_savings} liters")
    st.write(f"**Estimated Cost Savings:** ${cost_savings}")
    
    # Visual summary using an Altair bar chart
    metrics_df = pd.DataFrame({
        "Metric": [
            "Total Routes",
            "Total Emissions Saved (kg)",
            "Avg Emissions per Route (kg)",
            "Fuel Savings (liters)",
            "Cost Savings (USD)"
        ],
        "Value": [
            routes_simulated,
            total_emissions_saved,
            avg_emissions_saved,
            fuel_savings,
            cost_savings
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

    Enter your origin and destination below to calculate the best route. Our system retrieves the full route geometry, estimates travel details, and displays the path interactively.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("Enter Origin", "New York, NY")
    with col2:
        destination = st.text_input("Enter Destination", "Los Angeles, CA")
    
    if st.button("Simulate Route"):
        if origin and destination:
            origin_coords = get_coordinates(origin)
            destination_coords = get_coordinates(destination)
            if None in origin_coords or None in destination_coords:
                st.error("Could not geocode the provided addresses. Please try different inputs.")
            else:
                result = get_route_info(origin_coords, destination_coords)
                if result[0] is not None:
                    distance, duration, geometry = result
                    emissions_estimated = get_carbon_estimate(distance)
                    st.success(f"Optimized route from **{origin}** to **{destination}**:")
                    st.write(f"**Estimated Distance:** {distance:.2f} miles")
                    st.write(f"**Estimated Travel Time:** {duration:.2f} hours")
                    st.write(f"**Estimated CO₂ Emissions Saved:** {emissions_estimated:.2f} kg")
                    
                    # Update persistent metrics in Supabase (clearing cache inside update)
                    update_metrics_in_db(new_routes=1, new_emissions=emissions_estimated)
                    
                    if geometry:
                        # Calculate center for map view
                        lats = [coord[1] for coord in geometry]
                        lons = [coord[0] for coord in geometry]
                        avg_lat = sum(lats) / len(lats)
                        avg_lon = sum(lons) / len(lons)
                        
                        # Create a PathLayer to draw the route
                        route_layer = pdk.Layer(
                            "PathLayer",
                            data=[{"path": geometry, "name": "Route"}],
                            get_path="path",
                            get_color="[255, 0, 0, 255]",
                            width_scale=20,
                            width_min_pixels=2,
                            get_width=5,
                        )
                        view_state = pdk.ViewState(
                            latitude=avg_lat,
                            longitude=avg_lon,
                            zoom=6,
                            pitch=0,
                        )
                        deck = pdk.Deck(
                            layers=[route_layer],
                            initial_view_state=view_state,
                            tooltip={"text": "{name}"}
                        )
                        st.pydeck_chart(deck)
                    else:
                        st.error("Route geometry not available.")
                    
                    # Link sustainability metrics: fetch updated metrics and display a summary
                    updated_metrics = get_metrics_from_db()
                    st.markdown("### Updated Sustainability Impact")
                    st.write(f"**Total Routes Simulated:** {updated_metrics.get('routes_simulated', 0)}")
                    st.write(f"**Total CO₂ Emissions Saved:** {updated_metrics.get('total_emissions_saved', 0):.2f} kg")
                    st.write(f"**Estimated Fuel Savings:** {updated_metrics.get('fuel_savings', 0)} liters")
                    st.write(f"**Estimated Cost Savings:** ${updated_metrics.get('cost_savings', 0)}")
                    st.info("For a more detailed view, please check the 'Sustainability Metrics' page in the sidebar.")
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
