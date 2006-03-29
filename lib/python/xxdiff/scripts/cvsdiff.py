#!/usr/bin/env python
#******************************************************************************\
#* Copyright (C) 2003-2006 Martin Blais <blais@furius.ca>
#*
#* This program is free software; you can redistribute it and/or modify
#* it under the terms of the GNU General Public License as published by
#* the Free Software Foundation; either version 2 of the License, or
#* (at your option) any later version.
#*
#* This program is distributed in the hope that it will be useful,
#* but WITHOUT ANY WARRANTY; without even the implied warranty of
#* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#* GNU General Public License for more details.
#*
#* You should have received a copy of the GNU General Public License
#* along with this program; if not, write to the Free Software
#* Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#*
#*****************************************************************************/

"""xxdiff-cvs-diff [<options>] [<file> <file> ...]

This simple script invokes 'cvs diff' with the given file arguments, then splits
the output patch for individual files, applies the reverse patches to temporary
files and for each file it then spawns an xxdiff to preview each modified file
separately.  This allows you to preview the current changes that are made in a
cvs checkout.

Optionally, you can decide to accept changed and they are committed file by file
by this script.  In that case, the spawned xxdiff asks for a decision by the
user, then the script takes the following actions upon the answer:

- ACCEPT: keep the new file as it is and commit
- MERGED: copy the merged file on the new file and commit
- REJECT: don't do anything, keep the new file as it but do not commit.

For more generic behaviour about merging patches graphically, see also
xxdiff-patch.  The current script is really about committing "some" cvs changes.
"""

__version__ = "$Revision: 837 $"
__author__ = "Martin Blais <blais@furius.ca>"
__depends__ = ['xxdiff', 'Python-2.3', 'cvs', 'diffutils (patch)']
__copyright__ = """Copyright (C) 2003-2004 Martin Blais <blais@furius.ca>.
This code is distributed under the terms of the GNU General Public License."""


# stdlib imports.
import sys, os, os.path, re
import commands, shutil
from tempfile import NamedTemporaryFile


tmppfx = '%s.' % os.path.basename(sys.argv[0])

#-------------------------------------------------------------------------------
#
def splitpatch( text ):

    """Split output in chunks starting with ^Index.  Returns a list of pairs
    (tuples), each with (filename, patch) contents."""

    splitre = re.compile('^Index: (.*)$', re.M)
    chunks = []
    curbeg, curfn = None, None
    for mo in splitre.finditer(text):
        if curbeg != None:
            assert curfn
            chunks.append( (curfn, text[curbeg:mo.start()]) )
        curbeg = mo.start()
        curfn = mo.group(1)
    if curbeg != None:
        chunks.append( (curfn, text[curbeg:]) )

    return chunks

#-------------------------------------------------------------------------------
#
def complete( parser ):
    "Programmable completion support. Script should work without it."
    try:
        import optcomplete
        optcomplete.autocomplete(parser)
    except ImportError:
        pass


#-------------------------------------------------------------------------------
#
def main():
    import optparse
    parser = optparse.OptionParser(__doc__.strip(), version=__version__)
    parser.add_option('-c', '--commit', action='store_true',
                      help="ask for confirmation and commit accepted changes.")
    complete(parser)
    opts, args = parser.parse_args()

    # run cvs diff and read its output.
    cmd = 'cvs diff -u ' + ' '.join(map(lambda x: '"%s"' % x, args))
    s, o = commands.getstatusoutput(cmd)
    if s != 0 and not o:
        raise SystemExit("Error: running cvs command (%s): %s" % (s, cmd))
    chunks = splitpatch(o)

    #
    # For each subpatch, apply it individually
    #
    for filename, patch in chunks:
        ## print '*' * 80
        ## print fn
        ## print text

        # print patch contents for this file.
        print '*' * 40
        print patch
        print '*' * 40

        # feed diffs to patch, patch will do its deed and save the output to
        # a temporary file.
        tmpf = NamedTemporaryFile(prefix=tmppfx)
        cin, cout = os.popen2(
            'patch --reverse --output "%s"' % tmpf.name, 'rw')
        cin.write('Index: %s\n' % filename)
        cin.write(patch)
        # avoid "patch unexpectedly ends in middle of line" warning.
        if patch[-1] != '\n': 
            cin.write('\n')
        cin.close()

        # read output from patch.
        print cout.read()

        if not opts.commit:
            # simply invoke xxdiff on the files.
            os.system('xxdiff "%s" "%s"' % (tmpf.name, filename))
        else:
            # create temporary file to hold merged results.
            tmpf2 = NamedTemporaryFile('w', prefix=tmppfx)

            cmd = ('xxdiff --decision --merged-filename "%s" ' +
                   '--title2 "NEW FILE" "%s" "%s" ') % \
                   (tmpf2.name, tmpf.name, filename)
            s, o = commands.getstatusoutput(cmd)

            # print output of xxdiff command.
            if o:
                print o

            # if the user merged, copy the merged file over the original.
            if o == 'MERGED':
                # save a backup, in case.
                shutil.copyfile(filename, "%s.bak" % filename)
                shutil.copyfile(tmpf2.name, filename)

            if o == 'ACCEPT' or o == 'MERGED':
                # the user accepted, commit the file to CVS.
                os.system('cvs commit "%s"' % filename)
            elif o == 'REJECT' or o == 'NODECISION':
                pass # do nothing
            else:
                raise SystemExit(
                        "Error: unexpected answer from xxdiff: %s" % o)

if __name__ == '__main__':
    main()
