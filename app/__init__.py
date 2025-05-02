import os
from flask import Flask, jsonify, request, Response
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from flasgger import Swagger
from flask_cors import CORS
import time

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()

# Dictionary to track request counts for rate limiting
request_counts = {}
# How many requests allowed within the time window
RATE_LIMIT = 15
# Time window in seconds
RATE_LIMIT_WINDOW = 60

def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    # Enable CORS for all routes
    CORS(app)

    # Initialize Swagger for API documentation
    swagger = Swagger(app, template_file=os.path.join(os.path.dirname(__file__), 'swagger.yaml'))
    
    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        #SQLALCHEMY_DATABASE_URI=os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///instance/bank.db'),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI',
            f"sqlite:///{os.path.join(app.instance_path, 'bank.db')}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key'),
        JWT_ACCESS_TOKEN_EXPIRES=3600,  # 1 hour
    )
    
    # Enable debug mode
    app.debug = True

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    
    # Configure JWT handling
    @jwt.user_identity_loader
    def user_identity_lookup(identity):
        # Always convert identity to string for JWT
        return str(identity)
    
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        try:
            # Convert back to int for database lookup
            user_id = int(identity)
            from app.models.user import User
            return User.query.filter_by(id=user_id).one_or_none()
        except (ValueError, TypeError):
            return None
    
    # Error handling
    @jwt.expired_token_loader
    def expired_token_callback(_jwt_header, jwt_payload):
        return jsonify({"msg": "Token has expired"}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"msg": "Invalid token"}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"msg": "Authentication required"}), 401
        
    # In testing mode, make token expiration predictable
    if app.config.get('TESTING'):
        app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 1  # 1 second for tests

    # Add security headers
    @app.after_request
    def add_security_headers(response):
        # Skip Swagger UI routes
        if request.path.startswith('/apidocs') or request.path.startswith('/flasgger_static'):
            return response

        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response
    
    # Implement rate limiting
    @app.before_request
    def rate_limiting():
        # Skip rate limiting in test mode
        if app.config.get('TESTING'):
            return
        
        # Skip rate limiting for non-auth endpoints
        if not request.path.startswith('/api/auth') and not request.path.startswith('/api/login'):
            return
        
        # Get the client IP
        client_ip = request.remote_addr
        current_time = time.time()
        
        # Clean up old requests
        for ip in list(request_counts.keys()):
            request_counts[ip] = [req_time for req_time in request_counts[ip] 
                                  if current_time - req_time < RATE_LIMIT_WINDOW]
            if not request_counts[ip]:
                del request_counts[ip]
        
        # Check current request count
        if client_ip in request_counts and len(request_counts[client_ip]) >= RATE_LIMIT:
            return jsonify({"error": "Too many requests, please try again later"}), 429
        
        # Add current request
        if client_ip not in request_counts:
            request_counts[client_ip] = []
        request_counts[client_ip].append(current_time)

    # Register models
    from app.models import user, account, transaction

    # Register blueprints
    from app.routes import auth, accounts, transactions
    app.register_blueprint(auth.bp)
    app.register_blueprint(accounts.bp)
    app.register_blueprint(transactions.bp)
    
    # Root endpoint for testing
    @app.route('/')
    def home():
        return jsonify({"message": "Welcome to the Banking API"})

    # CLI commands
    @app.cli.command('init-db')
    def init_db_command():
        """Clear the existing data and create new tables."""
        db.drop_all()
        db.create_all()
        print('Initialized the database.')

    return app 