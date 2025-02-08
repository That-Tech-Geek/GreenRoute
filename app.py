import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pydeck as pdk
import requests
from datetime import datetime

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
    """Retrieve route info (distance in miles and duration in hours) using OSRM API."""
    # OSRM requires coordinates in lon,lat order.
    start_lon, start_lat = origin_coords[1], origin_coords[0]
    end_lon, end_lat = destination_coords[1], destination_coords[0]
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=false"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data and 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]
            distance = route['distance'] / 1609.34  # convert meters to miles
            duration = route['duration'] / 3600.0   # convert seconds to hours
            return distance, duration
    return None, None

def get_carbon_estimate(distance, vehicle_type='car'):
    """Estimate CO₂ emissions for a given distance (miles).
    (Example: an average car emits ~0.411 kg CO₂ per mile.)"""
    return distance * 0.411

def get_news_articles(query):
    """Fetch news articles using NewsAPI.
    Make sure to add your NewsAPI key in Streamlit's secrets under 'news_api_key'."""
    api_key = st.secrets.get("news_api_key", None)
    if not api_key:
        return []  # No API key provided, so no live news
    url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&apiKey={api_key}&language=en&pageSize=5"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        articles = data.get("articles", [])
        return articles
    return []

def save_feedback_to_airtable(name, email, feedback):
    """Save user feedback to Airtable using its REST API.
    Requires the following keys in st.secrets:
      - airtable_api_key
      - airtable_base_id
      - airtable_table_name (optional, defaults to 'Feedback')
    """
    api_key = st.secrets["airtable"]["airtable_api_key"]
    base_id = st.secrets["airtable"]["airtable_base_id"]
    table_name = st.secrets["airtable"].get("airtable_table_name", "Feedback")
    
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "fields": {
            "Name": name,
            "Email": email,
            "Feedback": feedback,
            "Timestamp": datetime.now().isoformat()
        }
    }
    response = requests.post(url, json=data, headers=headers)
    return response.status_code in [200, 201]

# ============================
# Page Configuration & Sidebar
# ============================
st.set_page_config(
    page_title="GreenRoute - Sustainable Logistics Dashboard",
    page_icon="🌱",
    layout="wide",
)

st.sidebar.title("Navigation")
pages = [
    "Overview", 
    "Competitor Analysis", 
    "Environmental Impact Tracker", 
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

    In today's competitive market, players such as **Magenta**, **ZeroNorth**, and **Pledge** are vying for leadership in sustainable logistics. 
    Our advantage lies in our holistic approach, leveraging AI and machine learning for personalized recommendations, environmental tracking, and educational support.
    """)
    st.image("https://images.unsplash.com/photo-1504384308090-c894fdcc538d", 
             caption="Sustainable Logistics in Action", use_column_width=True)
    st.markdown("### Explore the features from the sidebar to learn more!")

# ============================
# Competitor Analysis Page
# ============================
elif page == "Competitor Analysis":
    st.title("Competitor Analysis")
    st.markdown("### Market Overview")
    st.markdown("""
    **Key Competitors:**
    
    - **Magenta:** Specializes in electric mobility with significant funding.
    - **ZeroNorth:** Optimizes tramp shipping operations with a focus on maritime logistics.
    - **Pledge:** Provides comprehensive emissions management and fuel efficiency solutions.
    """)
    competitor_data = {
        "Competitor": ["Magenta", "ZeroNorth", "Pledge"],
        "Specialization": ["Electric Mobility", "Tramp Shipping Operations", "Emissions Management"],
        "Key Strength": ["Significant Funding", "Maritime Logistics Optimization", "Comprehensive Emissions Solutions"]
    }
    df_competitors = pd.DataFrame(competitor_data)
    st.table(df_competitors)

# ============================
# Environmental Impact Tracker Page
# ============================
elif page == "Environmental Impact Tracker":
    st.title("Environmental Impact Tracker")
    st.markdown("""
    **Monitor Your Environmental Impact**

    See real-time insights into CO₂ emissions. Adjust your logistics strategy to reduce your carbon footprint.
    """)
    dates = pd.date_range(end=datetime.today(), periods=30).to_pydatetime().tolist()
    emissions = np.random.normal(loc=50, scale=10, size=30)
    impact_data = pd.DataFrame({
        "Date": dates,
        "CO₂ Emissions (kg)": emissions
    })
    st.line_chart(impact_data.set_index("Date"))
    st.info("Use these insights to make data-driven decisions for reducing emissions.")

# ============================
# Personalized Recommendations Page
# ============================
elif page == "Personalized Recommendations":
    st.title("Personalized Recommendations")
    st.markdown("""
    **Tailored Solutions for Your Sustainability Goals**

    Provide your primary sustainability focus below to receive customized recommendations powered by our AI engine.
    """)
    user_goal = st.text_input("Enter your sustainability goal (e.g., reduce fuel consumption, minimize emissions):")
    if st.button("Get Recommendation"):
        if user_goal.strip():
            st.success(f"Based on your goal to **{user_goal.strip()}**, consider leveraging our optimization tools designed to enhance operational efficiency while lowering your carbon footprint.")
        else:
            st.warning("Please enter a sustainability goal to receive a personalized recommendation.")

# ============================
# Educational Content Page
# ============================
elif page == "Educational Content":
    st.title("Educational Content")
    st.markdown("""
    ### Dive into Sustainable Logistics
    
    **Sustainable Logistics:**  
    A holistic approach that minimizes environmental impact while optimizing supply chain operations. It integrates renewable energy, electric vehicles, and smart route planning.
    
    **Emissions Management:**  
    Involves tracking, analyzing, and reducing pollutants through cleaner fuels, optimized routes, and data-driven decision making.
    
    **The GreenRoute Edge:**  
    - **Personalized Insights:** Tailored recommendations for sustainability.
    - **Real-Time Tracking:** Monitor your environmental metrics.
    - **Learning Resources:** Stay updated on best practices and innovations.
    """)
    st.info("Educate yourself and empower your logistics operations with knowledge.")

# ============================
# Sustainability Metrics Page
# ============================
elif page == "Sustainability Metrics":
    st.title("Sustainability Metrics")
    st.markdown("### Comprehensive Metrics Dashboard")
    metrics = {
        "Total Emissions Reduced (kg)": np.random.randint(1000, 5000),
        "Fuel Savings (liters)": np.random.randint(200, 1000),
        "Cost Savings (USD)": np.random.randint(5000, 20000),
        "Optimized Routes": np.random.randint(50, 200)
    }
    st.subheader("Key Performance Indicators")
    st.write(metrics)
    df_metrics = pd.DataFrame({
        "Metric": list(metrics.keys()),
        "Value": list(metrics.values())
    })
    chart = alt.Chart(df_metrics).mark_bar().encode(
        x=alt.X("Metric:N", sort=None),
        y=alt.Y("Value:Q", title="Value"),
        color=alt.Color("Metric:N")
    ).properties(width=700, height=400)
    st.altair_chart(chart, use_container_width=True)
    st.info("Track these metrics to evaluate your sustainability performance over time.")

# ============================
# Route Optimization Simulator Page
# ============================
elif page == "Route Optimization Simulator":
    st.title("Route Optimization Simulator")
    st.markdown("""
    **Simulate Your Route and Estimate Environmental Impact**

    Input your origin and destination to simulate an optimized route using free APIs.
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
                route_info = get_route_info(origin_coords, destination_coords)
                if route_info:
                    distance, duration = route_info
                    emissions_estimated = get_carbon_estimate(distance)
                    st.success(f"Optimized route from **{origin}** to **{destination}**:")
                    st.write(f"**Estimated Distance:** {distance:.2f} miles")
                    st.write(f"**Estimated Travel Time:** {duration:.2f} hours")
                    st.write(f"**Estimated CO₂ Emissions (for a typical car):** {emissions_estimated:.2f} kg")
                    route_data = pd.DataFrame({
                        'lat': [origin_coords[0], destination_coords[0]],
                        'lon': [origin_coords[1], destination_coords[1]]
                    })
                    st.map(route_data)
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

    We fetch live news articles using a free API to keep you informed on the latest trends and innovations.
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
        st.info("No real-time news available. Please ensure you have set your News API key in st.secrets.")

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
                # Save feedback to Airtable
                success = save_feedback_to_airtable(name, email, feedback)
                if success:
                    st.success("Thank you for your feedback! It has been successfully saved.")
                else:
                    st.error("There was an error saving your feedback. Please try again later.")
            else:
                st.warning("Please fill in all fields before submitting.")
