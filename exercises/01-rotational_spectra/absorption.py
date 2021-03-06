"""Calculate and plot absorption cross sections."""
import re

import matplotlib.pyplot as plt
import numpy as np
import typhon as ty
import typhon.arts.workspace
from typhon.plots import styles


def main():
    # Define parameters
    species = "N2O"
    temperature = 300
    pressure = 800e2

    # Call ARTS to calculate absorption cross sections
    freq, abs_xsec = calculate_absxsec(species, pressure, temperature)

    # Plot the results.
    plt.style.use(styles("typhon"))

    fig, ax = plt.subplots()
    ax.plot(freq / 1e9, abs_xsec)
    ax.set_xlim(freq.min() / 1e9, freq.max() / 1e9)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Frequency [GHz]")
    ax.set_ylabel(r"Abs. cross section [$\sf m^2$]")
    ax.set_title(f"{tag2tex(species)} p:{pressure/100} hPa T:{temperature:0.0f} K")

    fig.savefig(  # Save figure.
        f"plots/plot_xsec_{species}_{pressure:.0f}Pa_{temperature:.0f}K.pdf"
    )
    plt.show()  # Open an interactive figure


def tag2tex(tag):
    """Replace all numbers in a species tag with LaTeX subscripts."""
    return re.sub("([a-zA-Z]+)([0-9]+)", r"\1$_{\2}$", tag)


def calculate_absxsec(
    species="N2O",
    pressure=800e2,
    temperature=300.0,
    fmin=10e9,
    fmax=2000e9,
    fnum=10_000,
    lineshape="LP",
    normalization="RQ",
    verbosity=2,
):
    """Calculate absorption cross sections.

    Parameters:
        species (str): Absorption species name.
        pressure (float): Atmospheric pressure [Pa].
        temperature (float): Atmospheric temperature [K].
        fmin (float): Minimum frequency [Hz].
        fmax (float): Maximum frequency [Hz].
        fnum (int): Number of frequency grid points.
        lineshape (str): Line shape model.
        normalization (str): Line shape normalization factor.
        verbosity (int): Set ARTS verbosity (``0`` prevents all output).

    Returns:
        ndarray, ndarray: Frequency grid [Hz], Abs. cross sections [m^2]
    """
    # Create ARTS workspace and load default settings
    ws = ty.arts.workspace.Workspace(verbosity=0)
    ws.execute_controlfile("general/general.arts")
    ws.execute_controlfile("general/continua.arts")
    ws.execute_controlfile("general/agendas.arts")
    ws.verbositySetScreen(ws.verbosity, verbosity)

    # We do not want to calculate the Jacobian Matrix
    ws.jacobianOff()

    # Agenda for scalar gas absorption calculation
    ws.Copy(ws.abs_xsec_agenda, ws.abs_xsec_agenda__noCIA)

    # Define absorption species
    ws.abs_speciesSet(species=[species])
    ws.ArrayOfIndexSet(ws.abs_species_active, [0])

    # Line catalogue: Perrin or HITRAN
    ws.ReadSplitARTSCAT(
        abs_species=ws.abs_species,
        basename="hitran/hitran_split_artscat5/",
        fmin=0.9 * fmin,
        fmax=1.1 * fmax,
        globalquantumnumbers="",
        localquantumnumbers="",
        ignore_missing=0,
    )

    # Set the lineshape function for all calculated tags
    ws.abs_linesSetLineShapeType(ws.abs_lines, lineshape)
    ws.abs_linesSetCutoff(ws.abs_lines, "None", 0.0)
    ws.abs_linesSetNormalization(ws.abs_lines, normalization)

    ws.abs_lines_per_speciesCreateFromLines()

    # Atmospheric settings
    ws.AtmosphereSet1D()

    # Setting the pressure, temperature and vmr
    ws.NumericSet(ws.rtp_pressure, float(pressure))  # [Pa]
    ws.NumericSet(ws.rtp_temperature, float(temperature))  # [K]
    ws.VectorSet(ws.rtp_vmr, np.array([1.0]))  # [VMR]
    ws.Touch(ws.abs_nlte)

    ws.AbsInputFromRteScalars()

    # Create a frequency grid
    ws.VectorNLinSpace(ws.f_grid, fnum, fmin, fmax)

    # isotop
    ws.isotopologue_ratiosInitFromBuiltin()

    # Calculate absorption cross sections
    ws.lbl_checkedCalc()
    ws.abs_xsec_agenda_checkedCalc()
    ws.abs_xsec_per_speciesInit()
    ws.abs_xsec_per_speciesAddLines()

    return ws.f_grid.value.copy(), ws.abs_xsec_per_species.value.copy()[0]


if __name__ == "__main__":
    main()
