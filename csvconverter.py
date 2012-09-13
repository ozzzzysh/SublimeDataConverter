"""
CSVConverter
package for Sublime Text 2

2012-09-13

https://github.com/fitnr/SublimeCSVConverter

Freely adapted from Mr. Data Converter: http://shancarter.com/data_converter/
"""

import sublime
import sublime_plugin
import csv
import os
import StringIO

PACKAGES = sublime.packages_path()


class CsvConvertCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):
        try:
            self.set_settings(kwargs)
        except Exception as e:
            print "CSV Converter: error fetching settings. Did you specify a format?", e
            return

        if self.view.sel()[0].empty():
            self.view.sel().add(sublime.Region(0, self.view.size()))

        for sel in self.view.sel():
            selection = self.view.substr(sel).encode('utf-8')
            data = self.import_csv(selection)
            converted = self.converter(data)
            self.view.replace(edit, sel, converted)

        self.view.set_syntax_file(self.syntax)

        if self.deselect_flag:
            self.deselect()

    def set_settings(self, kwargs):
        formats = {
            "html": {'syntax': PACKAGES + '/HTML/HTML.tmLanguage', 'function': self.html},
            "json": {'syntax': PACKAGES + '/JavaScript/JavaScript.tmLanguage', 'function': self.json},
            "json (array of columns)": {'syntax': PACKAGES + '/JavaScript/JavaScript.tmLanguage', 'function': self.jsonArrayCols},
            "json (array of rows)": {'syntax': PACKAGES + '/JavaScript/JavaScript.tmLanguage', 'function': self.jsonArrayRows},
            "python": {'syntax': PACKAGES + '/Python/Python.tmLanguage', 'function': self.python},
            "xml": {'syntax': PACKAGES + '/XML/XML.tmLanguage', 'function': self.xml},
            "xmlProperties": {'syntax': PACKAGES + '/XML/XML.tmLanguage', 'function': self.xmlProperties}
        }

        format = formats[kwargs['format']]
        self.converter = format['function']
        self.syntax = format['syntax']

        self.settings = sublime.load_settings(PACKAGES + '/CSVConverter/csvconverter.sublime-settings')

        # Combine headers for xml formats
        if kwargs['format'] == 'xml' or kwargs['format'] == 'xmlProperties':
            self.settings.set('merge_headers', True)

        # New lines
        self.newline = self.settings.get('line_sep', "\n")
        if self.newline == False:
            self.newline = os.line_sep

        # Indentation
        if (self.view.settings().get('translate_tabs_to_spaces')):
            self.indent = " " * int(self.view.settings().get('tab_size', 4))
        else:
            self.indent = "\t"

        # Option to deselect after conversion.
        self.deselect_flag = self.settings.get('deselect', True)

    def import_csv(self, selection):
        sample = selection[:1024]
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception as e:
            print "CSV Converter had trouble sniffing:", e
            delimiter = self.settings.get('delimiter', ",")
            try:
                csv.register_dialect('barebones', delimiter=delimiter)
            except Exception as e:
                print delimiter + ":", e

            dialect = csv.get_dialect('barebones')

        csvIO = StringIO.StringIO(selection)

        firstrow = sample.splitlines()[0].split(dialect.delimiter)

        # Replace spaces in the header names for some formats.
        r = self.settings.get('merge_headers', False)
        if r:
            firstrow = [x.replace(' ', '_') for x in firstrow]

        if self.settings.get('assume_headers', True) or csv.Sniffer().has_header(sample):
            self.headers = firstrow
        else:
            self.headers = ["val" + str(x) for x in range(len(firstrow))]

        reader = csv.DictReader(
            csvIO,
            fieldnames=self.headers,
            dialect=dialect)

        if self.headers == firstrow:
            reader.next()

        self.headers = self.parse(reader, self.headers)

        csvIO.seek(0)

        if self.headers == firstrow:
            reader.next()

        return reader

    #Adapted from https://gist.github.com/1608283
    def deselect(self):
        """Remove selection and place pointer at top of document."""
        top = self.view.sel()[0].a
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(top, top))

    # Parse data types
    # ==================
    def parse(self, reader, headers):
        headers_dict = dict((h, []) for h in headers)

        for n in range(10):
            row = reader.next()

            for i, header in zip(row, headers):
                typ = self.get_type(i)
                headers_dict['header'].append(typ)

        for header, type_list in headers_dict.items():
            if str in type_list:
                headers_dict[header] = str
            elif float in type_list:
                headers_dict[header] = float
            else:
                headers_dict[header] = int
        return headers_dict

    def get_type(self, datum):
        try:
            int(datum)
            return int
        except:
            try:
                float(datum)
                return float
            except:
                return str

    # Converters
    # ==========

    # Helper for HTML converter
    def tr(self, string):
        return (self.indent * 2) + "<tr>" + self.newline + string + (self.indent * 2) + "</tr>" + self.newline

    # HTML Table
    def html(self, datagrid):
        nl = self.newline
        ind = self.indent

        table = "<table>" + nl
        table += ind + "<thead>" + nl + "{0}</thead>" + nl
        table += ind + "<tbody>" + nl + "{1}</tbody>" + nl
        table += "</table>"

        # Render table head
        thead = ""
        for header in self.headers:
            thead += (ind * 3) + '<th>' + header + '</th>' + nl
        thead = self.tr(thead)

        # Render table rows
        tbody = ""
        for row in datagrid:
            rowText = ""

            # Sadly, dictReader doesn't always preserve row order,
            # so we loop through the headers instead.
            for key in self.headers:
                rowText += (ind * 3) + '<td>' + (row[key] or "") + '</td>' + nl

            tbody += self.tr(rowText)

        return table.format(thead, tbody)

    # JSON properties
    def json(self, datagrid):
        import json
        return json.dumps([row for row in datagrid])

    # JSON Array of Columns
    def jsonArrayCols(self, datagrid):
        import json
        colDict = {}
        for row in datagrid:
            for key, item in row.iteritems():
                if key not in colDict:
                    colDict[key] = []
                colDict[key].append(item)
        return json.dumps(colDict)

    # JSON Array of Rows
    def jsonArrayRows(self, datagrid):
        import json
        rowArrays = []

        for row in datagrid:
            itemlist = []
            for item in row.itervalues():
                itemlist.append(item)
            rowArrays.append(itemlist)

        return json.dumps(rowArrays)

    # Python dict
    def python(self, datagrid):
        out = []
        for row in datagrid:
            out.append(row)
        return repr(out)

    # XML Nodes
    def xml(self, datagrid):
        output_text = '<?xml version="1.0" encoding="UTF-8"?>' + self.newline
        output_text += "<rows>" + self.newline

        #begin render loop
        for row in datagrid:
            output_text += self.indent + "<row>" + self.newline
            for header in self.headers:
                line = (self.indent * 2) + '<{1}>{0}</{1}>' + self.newline
                item = row[header] or ""
                output_text += line.format(item, header)
            output_text += self.indent + "</row>" + self.newline

        output_text += "</rows>"

        return output_text

    # XML properties
    def xmlProperties(self, datagrid):
        output_text = '<?xml version="1.0" encoding="UTF-8"?>' + self.newline
        output_text += "<rows>" + self.newline

        #begin render loop
        for row in datagrid:
            row_list = []

            for header in self.headers:
                item = row[header] or ""
                row_list.append('{0}="{1}"'.format(header, item))
                row_text = " ".join(row_list)

            output_text += self.indent + "<row " + row_text + "></row>" + self.newline

        output_text += "</rows>"

        return output_text
