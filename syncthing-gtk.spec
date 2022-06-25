# See https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_example_spec_file

%define debug_package %{nil}

%define _name syncthing-gtk

%define mybuildnumber %{?build_number}%{?!build_number:1}

Name:           %{_name}
Version:        0.9.4.4.1
Release:        %{mybuildnumber}%{?dist}
Summary:        GTK3 & python based GUI for Syncthing

License:        GPLv2.0
URL:            https://github.com/Rudd-O/%{_name}
Source:         %{url}/archive/v%{version}/%{_name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  pyproject-rpm-macros

%global _description %{expand:
GTK3 & Python based GUI and notification area icon for Syncthing.

Supported Syncthing features

* Everything what WebUI can display
* Adding / editing / deleting nodes
* Adding / editing / deleting repositories
* Restart / shutdown server
* Editing daemon settings

Additional features

* First run wizard for initial configuration
* Running Syncthing daemon in background
* Half-automatic setup for new nodes and repositories
* Nautilus (a.k.a. Files), Nemo and Caja integration
* Desktop notifications}

%description %_description

%prep
%autosetup -p1 -n %{_name}-%{version}

%generate_buildrequires
%pyproject_buildrequires


%build
sed -i 's|#!.*|#!%{_bindir}/python3|'  scripts/%{name}
%pyproject_wheel


%install
%pyproject_install

%pyproject_save_files syncthing_gtk


%check
/bin/true


%files -n %{_name} -f %{pyproject_files}
%{_datadir}/%{name}
%{_datadir}/locale/*/*/%{name}.mo
%{_datadir}/metainfo/me.kozec.syncthingtk.appdata.xml
%{_datadir}/pixmaps/%{name}.png
%{_datadir}/icons/*/*/*/*syncthing*
%attr(0755, root, root) %{_bindir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/man/man1/%{name}*
%doc README.md


%changelog
* Sat Jun 25 2022 Manuel Amador <rudd-o@rudd-o.com> 0.9.4.4.1
- First RPM packaging release
