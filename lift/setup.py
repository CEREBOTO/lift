from setuptools import find_packages, setup

package_name = "lift"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            "share/" + package_name + "/scripts",
            ["scripts/keyboard_control", "scripts/keyboard_control.bash"],
        ),
    ],
    install_requires=["setuptools", "pyserial"],
    zip_safe=True,
    maintainer="OpenArm",
    maintainer_email="openarm_dev@enactic.ai",
    description="Pico lift PC serial console (ament_python).",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "keyboard_control = lift.control:main",
        ],
    },
)
