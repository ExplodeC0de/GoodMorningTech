from setuptools import setup

setup(
    name="newspaper",
    packages=["newspaper"],
    include_package_data=True,
    install_requires=[
        "Flask==2.2.2",
        "Flask-Mail==0.9.1",
        "Flask-SQLAlchemy==3.0.0",
        "email-validator==1.3.0",
        "beautifulsoup4==4.11.1",
        "requests==2.28.1",
    ],
)
