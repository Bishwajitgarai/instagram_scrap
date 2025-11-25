# Instagram Scraping API

A FastAPI-based application for scraping Instagram Reels and User data using Playwright.

## Features

- **Reels Scraping**: Fetch top reels from Instagram.
- **User Scraping**: Get user profile details.
- **Stealth Mode**: Uses `playwright-stealth` and `undetected-playwright` to avoid detection.
- **Headless Browser**: Runs in a headless Chromium instance for efficiency.
- **API Endpoints**: Clean RESTful API endpoints for easy integration.

## Prerequisites

- **Python**: >= 3.10
- **uv**: An extremely fast Python package installer and resolver.
- **Playwright**: Browser automation library.

## Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd instagram-scrap
    ```

2.  **Install dependencies using `uv`:**

    ```bash
    uv sync
    ```

3.  **Install Playwright browsers:**

    ```bash
    uv run playwright install
    ```

## Configuration

Create a `.env` file in the root directory. You can copy the example:

```bash
cp .env.example .env
```

Update the `.env` file with your configuration:

```ini
# Instagram Credentials (Optional for some public data, but recommended)
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password

# Browser Settings
HEADLESS=true
USER_DATA_DIR=./instagram_profile
BROWSER_TIMEOUT=60000
NAVIGATION_TIMEOUT=45000
DEFAULT_TIMEOUT=45000

# API Settings
API_HOST=0.0.0.0
API_PORT=9010

# Scraping Settings
TOP_REELS_DEFAULT=12
MAX_PAGINATION_ITERATIONS=50
PAGINATION_DELAY=1.0
```

## Usage

### Running the Server

Start the FastAPI server:

```bash
uv run python main.py
```

Or using `uvicorn` directly (if installed in the environment):

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 9010 --reload
```

The API will be available at `http://localhost:9010`.

### Running with Docker

You can also run the application using Docker.

#### Using Docker Compose (Recommended)

1.  Ensure you have Docker and Docker Compose installed.
2.  Run the application:

    ```bash
    docker-compose up --build
    ```

The API will be available at `http://localhost:9010`.

#### Manual Docker Build

1.  Build the image:

    ```bash
    docker build -t instagram-scrap .
    ```

2.  Run the container:

    ```bash
    docker run -p 9010:9010 --env-file .env instagram-scrap
    ```

### API Documentation

Once the server is running, you can access the interactive API documentation (Swagger UI) at:

-   **Swagger UI**: `http://localhost:9010/docs`
-   **ReDoc**: `http://localhost:9010/redoc`

### Example Endpoints

-   **Get Top Reels**: `GET /v1/reels/top`
-   **Get User Info**: `GET /v1/user/{username}`

## Project Structure

```
instagram-scrap/
├── app/
│   ├── core/           # Configuration and settings
│   ├── routes/         # API route definitions
│   │   └── v1/         # Version 1 routes
│   └── server/         # Server setup
├── instagram_profile/  # Browser user data (ignored by git)
├── main.py             # Application entry point
├── pyproject.toml      # Project dependencies and config
├── uv.lock             # Dependency lock file
└── README.md           # Project documentation
```

## License

[Add your license here, e.g., MIT]