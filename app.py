import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pydeck as pdk
from datetime import datetime

# ---------------------------
# Page Configuration
# ---------------------------
st.set_page_config(
    page_title="GreenRoute - Sustainable Logistics Dashboard",
    page_icon="🌱",
    layout="wide",
)

# ---------------------------
# Sidebar Navigation
# ---------------------------
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

# ---------------------------
# Overview Page
# ---------------------------
if page == "Overview":
    st.title("GreenRoute: Revolutionizing Sustainable Logistics")
    st.markdown("""
    **Welcome to GreenRoute!**

    In today's competitive market, players such as **Magenta**, **ZeroNorth**, and **Pledge** are vying for leadership in sustainable logistics. 
    Our advantage lies in our holistic approach, leveraging AI and machine learning for personalized recommendations, environmental tracking, and educational support.
    """)
    st.image("https://images.unsplash.com/photo-1504384308090-c894fdcc538d", caption="Sustainable Logistics in Action", use_column_width=True)
    st.markdown("### Explore the features from the sidebar to learn more!")

# ---------------------------
# Competitor Analysis Page
# ---------------------------
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

# ---------------------------
# Environmental Impact Tracker Page
# ---------------------------
elif page == "Environmental Impact Tracker":
    st.title("Environmental Impact Tracker")
    st.markdown("""
    **Monitor Your Environmental Impact**

    See real-time insights into CO₂ emissions. Adjust your logistics strategy to reduce your carbon footprint.
    """)
    
    # Generate simulated data for the past 30 days
    dates = pd.date_range(end=datetime.today(), periods=30).to_pydatetime().tolist()
    emissions = np.random.normal(loc=50, scale=10, size=30)
    impact_data = pd.DataFrame({
        "Date": dates,
        "CO₂ Emissions (kg)": emissions
    })
    
    # Line Chart Visualization
    st.line_chart(impact_data.set_index("Date"))
    st.info("Use these insights to make data-driven decisions for reducing emissions.")

# ---------------------------
# Personalized Recommendations Page
# ---------------------------
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

# ---------------------------
# Educational Content Page
# ---------------------------
elif page == "Educational Content":
    st.title("Educational Content")
    st.markdown("""
    ### Dive into Sustainable Logistics
    
    **Sustainable Logistics:**  
    A holistic approach that minimizes environmental impact while optimizing supply chain operations. It integrates renewable energy, electric vehicles, and smart route planning.
    
    **Emissions Management:**  
    Encompasses tracking, analyzing, and reducing pollutants through cleaner fuels, optimized routes, and data-driven decision making.
    
    **The GreenRoute Edge:**  
    - **Personalized Insights:** Tailored recommendations for sustainability.
    - **Real-Time Tracking:** Monitor your environmental metrics.
    - **Learning Resources:** Stay updated on best practices and innovations.
    """)
    st.info("Educate yourself and empower your logistics operations with knowledge.")

# ---------------------------
# Sustainability Metrics Page (New)
# ---------------------------
elif page == "Sustainability Metrics":
    st.title("Sustainability Metrics")
    st.markdown("### Comprehensive Metrics Dashboard")
    
    # Simulated Metrics
    metrics = {
        "Total Emissions Reduced (kg)": np.random.randint(1000, 5000),
        "Fuel Savings (liters)": np.random.randint(200, 1000),
        "Cost Savings (USD)": np.random.randint(5000, 20000),
        "Optimized Routes": np.random.randint(50, 200)
    }
    st.subheader("Key Performance Indicators")
    st.write(metrics)
    
    # Altair Bar Chart for Visual Comparison
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

# ---------------------------
# Route Optimization Simulator Page (New)
# ---------------------------
elif page == "Route Optimization Simulator":
    st.title("Route Optimization Simulator")
    st.markdown("""
    **Simulate Your Route and Estimate Environmental Impact**

    Input your origin and destination to simulate an optimized route. We will estimate distance, travel time, and potential emissions savings.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("Enter Origin", "New York, NY")
    with col2:
        destination = st.text_input("Enter Destination", "Los Angeles, CA")
    
    if st.button("Simulate Route"):
        if origin and destination:
            # Dummy calculations for simulation
            distance = np.random.randint(2500, 3000)  # miles
            travel_time = distance / np.random.uniform(50, 70)  # hours
            emissions_saved = np.random.randint(100, 500)  # kg CO₂ saved
            st.success(f"Optimized route from **{origin}** to **{destination}**:")
            st.write(f"**Estimated Distance:** {distance} miles")
            st.write(f"**Estimated Travel Time:** {travel_time:.1f} hours")
            st.write(f"**Potential CO₂ Emissions Saved:** {emissions_saved} kg")
            
            # Simulate a route map with dummy coordinates (random example)
            route_data = pd.DataFrame({
                'lat': [40.7128, 34.0522],
                'lon': [-74.0060, -118.2437]
            })
            st.map(route_data)
        else:
            st.warning("Please enter both origin and destination to simulate the route.")

# ---------------------------
# Real-Time News Page (New)
# ---------------------------
elif page == "Real-Time News":
    st.title("Real-Time News")
    st.markdown("""
    **Stay Updated with the Latest in Sustainable Logistics**

    Below are some simulated news headlines and summaries on the latest trends and innovations in sustainable logistics.
    """)
    
    # Dummy news items
    news_items = [
        {
            "title": "GreenRoute Launches New AI-Driven Optimization Tool",
            "summary": "GreenRoute unveils a cutting-edge AI system that personalizes route optimization for businesses, reducing emissions and operational costs.",
            "link": "https://example.com/greenroute-ai"
        },
        {
            "title": "Electric Mobility on the Rise",
            "summary": "Magenta continues to secure funding as the electric mobility market expands, promising a cleaner future for urban transport.",
            "link": "https://example.com/magenta-funding"
        },
        {
            "title": "Innovations in Maritime Logistics",
            "summary": "ZeroNorth's latest updates bring significant improvements to tramp shipping operations, enhancing efficiency and sustainability.",
            "link": "https://example.com/zeronorth-maritime"
        }
    ]
    
    for news in news_items:
        st.subheader(news["title"])
        st.write(news["summary"])
        st.markdown(f"[Read more]({news['link']})")
        st.markdown("---")
    
    st.info("Note: These news items are simulated for demonstration purposes.")

# ---------------------------
# User Feedback Page (New)
# ---------------------------
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
            st.success("Thank you for your feedback!")
            # Here you could add code to save the feedback to a database or send via email.
