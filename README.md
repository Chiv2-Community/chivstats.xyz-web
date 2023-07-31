# ChivStats.xyz Web

[ChivStats.xyz](https://chivstats.xyz/) is the web frontend for the Chivalry 2 player leaderboard project. It provides an interface to view and interact with player statistics and leaderboards for the game Chivalry 2. This frontend connects to a backend SQL server that stores player statistics, which are pulled from Torn Banner's official data sources. The polling and storage process is separate from this web frontend.

## Overview

The ChivStats.xyz web application serves as a user-friendly interface to access and explore Chivalry 2 player statistics. By connecting to a backend SQL server, it retrieves and displays data related to player statistical data. Another backend process is responsible for polling the official game data sources and storing the information, while this frontend focuses on presenting the data in an accessible and visually appealing manner. 

## Structure

A sample of the backend data can be found here: [Sample DB data 500K rows](https://chivstats.xyz/static/samplechivstats.zip)

### Main Components

- **chivstats**: The main configuration for the Django web application.
- **leaderboards**: Contains the logic and templates for displaying leaderboards and player statistics.

### Key Directories

- **chivstats**: Contains the main settings and configuration files for the Django application.
- **leaderboards**: Includes the views, models, serializers, and templates for the leaderboards.
- **static**: Houses static files such as CSS, JavaScript, and images.

### Templates

The templates for the leaderboards are located under `leaderboards/templates/leaderboards` and include:

- **index.html**: The main landing page.
- **leaderboard.html**: Displays the leaderboard.
- **playerprofile.html**: Shows individual player profiles.
- **top_players.html**: Lists the top players.

### Static Files

Static files are organized under the `static` directory, including:

- **admin**: Contains CSS, fonts, images, and JavaScript for the admin interface.
- **debug_toolbar**: Includes CSS and JavaScript for the Django Debug Toolbar.
- **favicon.ico**: The favicon for the website.

## Requirements

The required packages for the project can be found in `requirements.txt`.

## Running the Project

To run the project, you'll need to have Django installed and configured. You can follow the standard Django project setup, including applying migrations and running the development server.

## Contributing

Contributions to the project are welcome! Feel free to open an issue or submit a pull request.

## License

Ask gimmic.
