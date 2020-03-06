"""IDP Conf Gen Exceptions."""
from idpconfgen import contactus as CONTACTUS
from idpconfgen.core import has_string_formatters


class IDPConfGenException(Exception):
    r"""
    IDPConfGen base exception.

    Example:

        >>> err = IDPCalculator(var1, var2)
        
        >>> err = IDPConfGenException('An error happened: {}, {}', var1, var2)
        
        >>> err = IDPConfGenException(errmsg='Custom error msg')
        
        >>> err = IDPConfGenException(errmsg='')

    Parameters
    ----------
    *args
        If the first element of args contains ``'{}'`` it will be
        used as :attr:`errmsg` base string.
        Else, ``args`` are used to feed the sting method ``.format()``
        for the default exception :attr:`errmsg`.

    errmsg : optional
        If given, overrides any previous parameter and the ``str``
        value of ``errmsg`` is used as the Exception message.
        Defaults to ``None``.
    """

    errmsg = 'An unknnown error as occurred. ' + CONTACTUS.contact_message

    def __init__(self, *args, errmsg=None):
    
        # require
        if errmsg:
            self.errmsg = str(errmsg)
            self.args = []

        elif args and has_string_formatters(args[0]):
            self.errmsg = args[0]
            self.args = args[1:]

        else:
            self.args = args

        # ensure
        assert self.errmsg.count('{}') == len(self.args)
     
    def __str__(self):
        """Make me a string :-)."""
        return self.errmsg.format(*self.args)

    def report(self):
        """
        Report error in the form of a string.
        
        Identifies Error type and error message.
        
        Returns
        -------
        str
            The formatted string report.
        """
        return f'{self.__class__.__name__} * {self}'


class PDBIDFactoryError(IDPConfGenException):
    """General PDBIDFactory Exception."""

    pass


class DownloadFailedError(IDPConfGenException):
    """Raise when download fails."""

    pass


class EmptyFilterError(IDPConfGenException):
    """Raise when PDB data filtering returns an empty selection."""

    errmsg = 'Filter returns empty selection.'


class DSSPParserError(IDPConfGenException):
    """Raise when libs.libparse.DSSPParserError needs it."""

    errmsg = 'Error while parsing {}'


class DSSPSecStructError(IDPConfGenException):
    """Raise when libs.libparse.DSSPParserError needs it."""

    errmsg = 'Values differ from possible DSSP secondary structure keys.'


class DSSPInputMissingError(IDPConfGenException):
    """Raise when libs.libparse.DSSPParserError needs it."""

    errmsg = 'One of the two required positional arguments is missing.'