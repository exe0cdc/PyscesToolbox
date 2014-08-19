import numpy as np
#from PyscesToolBox import PyscesToolBox as PYCtools
from sympy import Symbol
#from IPython.display import Latex
from ...utils.misc import silence_print
from ...utils.plotting import LineData, ScanFig


def cctype(obj):
    return 'ccobjects' in str(type(obj))


@silence_print
def get_state(mod, do_state=False):
    if do_state:
        mod.doState()
    ss = [getattr(mod, 'J_' + r) for r in mod.reactions] + \
        [getattr(mod, s + '_ss') for s in mod.species]
    return ss


@silence_print
def silent_mca(mod):
    mod.doMca()


class StateKeeper:
    def __init__(self, state):
        self._last_state_for_mca = state

    def do_mca_state(self, mod, state):
        if state != self._last_state_for_mca:
            silent_mca(mod)
            self._last_state_for_mca = state


class CCBase(object):

    """The base object for the control coefficients and control patterns"""

    def __init__(self, mod, name, expression, ltxe, state_keeper):
        super(CCBase, self).__init__()

        self.expression = expression
        self.mod = mod
        self._ltxe = ltxe
        self._state_keeper = state_keeper
        self.name = name
        self._latex_name = '\\Sigma'

        self._value = None
        self._latex_expression = None
        self._state_ = get_state(mod)

    @property
    def latex_expression(self):
        if not self._latex_expression:
            self._latex_expression = self._ltxe.expression_to_latex(
                self.expression
            )
        return self._latex_expression

    @property
    def latex_name(self):
        return self._latex_name

    @property
    def value(self):
        """The value property. Calls self._calc_value() when self._value
        is None and returns self._value"""
        new_ss = get_state(self.mod)
        state_changed = new_ss != self._state_
        if state_changed:
            self._state_keeper.do_mca_state(self.mod, new_ss)
            self._calc_value()
            self._state_ = new_ss
        elif not self._value:
            self._calc_value()
        return self._value

    def _repr_latex_(self):
        return '$%s = %s = %.3f$' % (self.latex_name,
                                     self.latex_expression,
                                     self.value)

    def _calc_value(self):
        """Calculates the value of the expression"""
        symbols = self.expression.atoms(Symbol)
        subsdic = {}
        for symbol in symbols:
            subsdic[symbol] = getattr(self.mod, str(symbol))
        self._value = self.expression.subs(subsdic)

    def __repr__(self):
        return self.expression.__repr__()

    def __add__(self, other):
        if cctype(other):
            return self.expression.__add__(other.expression)
        else:
            return self.expression.__add__(other)

    def __mul__(self, other):
        if cctype(other):
            return self.expression.__mul__(other.expression)
        else:
            return self.expression.__mul__(other)

    def __div__(self, other):
        if cctype(other):
            return self.expression.__div__(other.expression)
        else:
            return self.expression.__div__(other)

    def __pow__(self, other):
        if cctype(other):
            return self.expression.__pow__(other.expression)
        else:
            return self.expression.__pow__(other)


class CCoef(CCBase):

    """The object the stores control coefficients. Inherits from CCBase"""

    def __init__(self, mod, name, expression, denominator, ltxe, state_keeper):
        super(CCoef, self).__init__(mod, name, expression, ltxe, state_keeper)
        self.numerator = expression
        self.denominator = denominator.expression
        self.expression = self.numerator / denominator.expression
        self.denominator_object = denominator

        self._latex_numerator = None
        self._latex_expression_full = None
        self._latex_expression = None
        self._latex_name = None

        self.control_patterns = None

        self._set_control_patterns()

    @property
    def latex_numerator(self):
        if not self._latex_numerator:
            self._latex_numerator = self._ltxe.expression_to_latex(
                self.numerator
            )
        return self._latex_numerator

    @property
    def latex_expression_full(self):
        if not self._latex_expression_full:
            full_expr = '\\frac{' + self.latex_numerator + '}{' \
                + self.denominator_object.latex_expression + '}'
            self._latex_expression_full = full_expr
        return self._latex_expression_full

    @property
    def latex_expression(self):
        if not self._latex_expression:
            self._latex_expression = self.latex_numerator + '/ \\,\\Sigma'
        return self._latex_expression

    @property
    def latex_name(self):
        if not self._latex_name:
            self._latex_name = self._ltxe.expression_to_latex(
                self.name
            )
        return self._latex_name

    #@property
    # def control_patterns(self):
    #    if not self._control_patterns:
    #        self._set_control_patterns()
    #    return self._control_patterns

    def parscan(self, parameter, scan_range, scan_type='percentage', init_return=False):
        """Performs a parameter scan and returns numpy array object
           with the parameter values in the first column and
           percentage contribution of each control pattern
           in subsequent columns

           Arguments:
           parameter   --  the parameter of the model to scan
           scan_range  --  the range across which to scan 'parameter'

           calls self._recalculate_value() for each value of
           parameter in scan_range"""

        assert scan_type in ['percentage', 'value']
        if scan_type is 'percentage':
            scan_res = [list() for i in range(len(self.control_patterns) + 1)]
        elif scan_type is 'value':
            scan_res = [list() for i in range(len(self.control_patterns) + 2)]
        scan_res[0] = scan_range

        # print type(scan_res)
        init = getattr(self.mod, parameter)
        for parvalue in scan_range:
            setattr(self.mod, parameter, parvalue)
            self.mod.SetQuiet()
            self.mod.doMca()
            self.mod.SetLoud()


            for i, cp in enumerate(self.control_patterns):
                # print type(scan_res[i+1])
                if scan_type is 'percentage':
                    scan_res[i + 1].append(cp.percentage)
                elif scan_type is 'value':
                    scan_res[i + 1].append(cp.value)

            if scan_type is 'value':
                scan_res[i + 2].append(self.value)

        if init_return:
            setattr(self.mod, parameter, init)

        cp_names = [cp.name for cp in self.control_patterns]
        data = np.array(scan_res, dtype=np.float).transpose()
        line_data_list = []
        for i, cp in enumerate(cp_names):
            ld = LineData(name=cp,
                          x_data=data[:, 0],
                          y_data=data[:, 1+i],
                          categories=[cp])
            line_data_list.append(ld)

        if scan_type is 'value':
                ld = LineData(name='$%s$' % self.latex_name,
                              x_data=data[:, 0],
                              y_data=data[:,2 + i],
                              categories=[self.name])
                line_data_list.append(ld)

        if parameter in self.mod.fixed_species:
            x_label = '[%s]' % parameter.replace('_', ' ')
        else:
            x_label = '%s' % parameter.replace('_', ' ')
        if scan_type is 'percentage':
            y_label = 'Percentage Contribution'
            cat_classes = {'Control Patterns': cp_names}
        elif scan_type is 'value':
            y_label = 'Control coefficient/pattern value'
            cat_classes = {'Control Coefficient/Patterns': cp_names + [self.name]}


        scan_fig = ScanFig(line_data_list,
                           ax_properties={'xlabel': x_label,
                                          'ylabel': y_label,
                                          'xscale': 'log',
                                          'xlim': [np.min(scan_range),
                                                   np.max(scan_range)],},
                           category_classes=cat_classes)

        return scan_fig


    def _recalculate_value(self):
        """Recalculates the control coefficients and control pattern
           values. calls _calc_value() for self and each control
           pattern. Useful for when model parameters change"""
        for pattern in self.control_patterns:
            pattern._calc_value()
        self._calc_value()

    def _calc_value(self):
        """Calculates the numeric value of the control pattern from the
           values of its control patterns."""
        self._value = sum([pattern.value for pattern in self.control_patterns])

    def _set_control_patterns(self):
        """Divides control coefficient into control patterns and saves
           results in self.CPx where x is a number is the number of the
           control pattern as it appears in in control coefficient
           expression"""
        patterns = self.numerator.as_coeff_add()[1]
        cps = []
        for i, pattern in enumerate(patterns):
            name = 'CP' + str(1 + i)
            cp = CPattern(self.mod,
                          name,
                          pattern,
                          self.denominator_object,
                          self,
                          self._ltxe,
                          self._state_keeper)
            setattr(self, name, cp)
            cps.append(cp)
        self.control_patterns = cps
        #assert self._check_control_patterns == True

    def _check_control_patterns(self):
        """Checks that all control patterns are either positive or negative"""
        all_same = False
        poscomp = [i.value > 0 for i in self.control_patterns]
        negcomp = [i.value < 0 for i in self.control_patterns]
        if all(poscomp):
            all_same = True
        elif all(negcomp):
            all_same = True
        return all_same


class CPattern(CCBase):

    """docstring for CPattern"""

    def __init__(self,
                 mod,
                 name,
                 expression,
                 denominator,
                 parent,
                 ltxe,
                 state_keeper):
        super(CPattern, self).__init__(mod,
                                       name,
                                       expression,
                                       ltxe,
                                       state_keeper)
        self.numerator = expression
        self.denominator = denominator.expression
        self.expression = self.numerator / denominator.expression
        self.denominator_object = denominator
        self.parent = parent

        self._latex_numerator = None
        self._latex_expression_full = None
        self._latex_expression = None
        self._latex_name = None
        self._percentage = None

    @property
    def latex_numerator(self):
        if not self._latex_numerator:
            self._latex_numerator = self._ltxe.expression_to_latex(
                self.numerator
            )
        return self._latex_numerator

    @property
    def latex_expression_full(self):
        if not self._latex_expression_full:
            full_expr = '\\frac{' + self.latex_numerator + '}{' \
                + self.denominator_object.latex_expression + '}'
            self._latex_expression_full = full_expr
        return self._latex_expression_full

    @property
    def latex_expression(self):
        if not self._latex_expression:
            self._latex_expression = self.latex_numerator + '/ \\,\\Sigma'
        return self._latex_expression

    @property
    def latex_name(self):
        if not self._latex_name:
            self._latex_name = self.name
        return self._latex_name

    @property
    def percentage(self):
        self._percentage = (self.value / self.parent.value) * 100
        return self._percentage
