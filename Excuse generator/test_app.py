#!/usr/bin/env python3
"""
Simple test script for the AI Excuse Generator
Run this to verify the application is working correctly
"""

import os
import sys
import requests
import time

def test_flask_app():
    """Test if the Flask application is running and responding"""
    try:
        # Wait a moment for the app to start
        time.sleep(2)
        
        # Test the home page
        response = requests.get('http://localhost:5000/', timeout=5)
        if response.status_code == 200:
            print("✅ Home page is accessible")
            return True
        else:
            print(f"❌ Home page returned status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask application")
        print("   Make sure the app is running with: python app.py")
        return False
    except Exception as e:
        print(f"❌ Error testing application: {e}")
        return False

def test_dependencies():
    """Test if all required dependencies are available"""
    required_packages = [
        'flask',
        'openai',
        'flask_sqlalchemy',
        'flask_login',
        'pillow',
        'gtts',
        'faker'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} is available")
        except ImportError:
            print(f"❌ {package} is missing")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📦 Install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def test_environment():
    """Test environment configuration"""
    print("\n🔧 Environment Configuration:")
    
    # Check if .env file exists
    if os.path.exists('.env'):
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found")
        print("   Copy env_example.txt to .env and configure your OpenAI API key")
    
    # Check OpenAI API key
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key and openai_key != 'your-openai-api-key-here':
        print("✅ OpenAI API key is configured")
    else:
        print("⚠️  OpenAI API key not configured")
        print("   Set OPENAI_API_KEY in your .env file")
    
    # Check secret key
    secret_key = os.getenv('SECRET_KEY')
    if secret_key and secret_key != 'your-secret-key-here':
        print("✅ Secret key is configured")
    else:
        print("⚠️  Secret key not configured")
        print("   Set SECRET_KEY in your .env file")

def main():
    """Main test function"""
    print("🤖 AI Excuse Generator - Application Test")
    print("=" * 50)
    
    # Test dependencies
    print("\n📦 Testing Dependencies:")
    deps_ok = test_dependencies()
    
    # Test environment
    test_environment()
    
    # Test Flask app if dependencies are ok
    if deps_ok:
        print("\n🌐 Testing Flask Application:")
        app_ok = test_flask_app()
        
        if app_ok:
            print("\n🎉 All tests passed! Your AI Excuse Generator is ready to use.")
            print("\n📱 Open your browser and go to: http://localhost:5000")
            print("👤 Register a new account to start generating excuses!")
        else:
            print("\n❌ Flask application test failed")
            print("   Make sure to run: python app.py")
    else:
        print("\n❌ Dependency test failed")
        print("   Install missing packages before running the application")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()
