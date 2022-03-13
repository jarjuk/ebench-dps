import setuptools

import ebenchDps.CMDS as CMDS


with open("VERSION", "r") as fh:
    version = fh.read().rstrip()

name="ebenchDps"

print( "version", version, ", packages", setuptools.find_packages())
    
setuptools.setup(
    name=name, # Replace with your own username
    packages=setuptools.find_packages(),
    version=version,
    zip_safe= True,
    install_requires = [ "pyvisa-py", "absl-py",  ],
    author="jj",
    author_email="author@example.com",
    description="ebDps5020 - DPS5020 - Digital Control Power Supply controller",
    long_description="",
    long_description_content_type="text/markdown",
    url="https://github.com/jarjuk/ebench-dps",
    package_data={
        "ebenchDps": ['../VERSION', '../RELEASES.md' ]
    },
    entry_points = {
        "console_scripts": [ f"{CMDS.CMD_DPS}=ebenchDps.ebenchDps_main:main"
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
)
