from setuptools import setup, find_packages

setup(
    name="sslh",
    version='2.0.0',
    url="https://github.com/BioplatformsAustralia/sslh",
    author="Bioplatforms Australia",
    author_email="help@bioplatforms.com",

    description="Handle (generalising or suppressing as required) the location of sensitive species.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',

    zip_safe=True,
    install_requires=["shapely", "fiona"],

    packages=['sslh'],
    package_dir={'sslh': 'sslh/'},
    package_data={'sslh': [
        'data/*', 'data/shapefiles/PSMA/*/*']},
    classifiers=[
        "Framework :: Python",
        "Intended Audience :: Developers",
        "License :: GPL license",
        "Topic :: Software Development",
        'Programming Language :: Python :: 3.6',
    ],
    setup_requires=["pytest-runner"],
    tests_require=["pytest"]
)
