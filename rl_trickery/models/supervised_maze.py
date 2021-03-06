from .tricky_policy_networks import *
from .muzero import DynamicsNetwork

class MazeSolver(nn.Module):
    def __init__(
            self,
            obs_space,
            architecture,
            state_channels=32,
            hidden_size=128,
            fixed_recursive_depth=1,
            append_coords=False,
            pool_and_inject=False,
            skip_connection=False,
            spatial_state_size=7
    ):
        super(MazeSolver, self).__init__()

        init_relu = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0),
                                   nn.init.calculate_gain('relu'))

        self.hidden_size = hidden_size
        self.architecture = architecture
        self.is_recurrent = architecture in ["rnn", "crnn"]
        self.spatial_state_shape = (spatial_state_size, spatial_state_size) if architecture == "crnn" else ()  # dictated by layer choice in encoder

        self.encoder = Encoder(obs_space, hidden_size, state_channels, append_coords=append_coords)

        if architecture == "ff":
            self.transition = NoTransition(hidden_size)
        elif architecture == "rnn":
            self.transition = RNNTransition(
                hidden_size=hidden_size,
                recurse_depth=fixed_recursive_depth,
                skip_connection=skip_connection,
            )
        elif architecture == "crnn":
            self.transition = CRNNTransition(
                state_channels=state_channels,
                spatial_shape=self.spatial_state_shape,
                recurse_depth=fixed_recursive_depth,
                append_coords=append_coords,
                pool_inject=pool_and_inject,
                skip_connection=skip_connection,
            )
        else:
            raise NotImplementedError

        self.enc2trans = DimensionalityAdjuster(
            in_shape=self.encoder.out_shape,
            out_shape=self.transition.in_shape
        )

        self.trans2ac = DimensionalityAdjuster(
            in_shape=self.transition.out_shape,
            out_shape=np.array((hidden_size,))
        )

        self.lin_out = nn.Sequential(
            init_relu(nn.Linear(hidden_size, 1, )),
        )

        self.train()

    def recurrent_hidden_state_size(self):
        if self.is_recurrent:
            return self.transition.recurrent_hidden_state_size
        else:
            return (0,)

    def forward(self, obs, rnn_h, done):
        x = self.encoder(obs)
        x_enc = self.enc2trans(x)
        x_trans, rnn_h = self.transition(x_enc, rnn_h, done, None)
        x_ac = self.trans2ac(x_trans)
        out = self.lin_out(x_ac)
        return out, rnn_h


class SeqSolverRNN(nn.Module):
    def __init__(
            self,
            obs_space,
            state_channels=32,
    ):
        super(SeqSolverRNN, self).__init__()

        n_channels = obs_space.shape[0]
        im_size = obs_space.shape[1]

        init_relu = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0),
                                   nn.init.calculate_gain('relu'))

        self.encoder = nn.Sequential(
            init_relu(nn.Conv2d(n_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            Flatten(),
            init_relu(nn.Linear(state_channels * im_size * im_size, 256)),
            nn.ReLU(),
        )

        self.recurse = nn.LSTMCell(256, 256)

        self.out_layers = nn.Sequential(
            init_relu(nn.Linear(256, 256)),
            nn.ReLU(),
            init_relu(nn.Linear(256, 1)),
        )

    def forward(self, obs, recurse_depth=5):
        h = self.encoder(obs)

        outputs = []
        rnn_out = None
        for i in range(recurse_depth):
            rnn_out = self.recurse(h, rnn_out)
            h_cur, c_cur = rnn_out
            out = self.out_layers(h_cur)
            outputs.append(out)

        outputs = torch.stack(outputs)
        return outputs


class SeqSolverFF12(nn.Module):
    def __init__(
            self,
            obs_space,
            state_channels=32,
    ):
        super(SeqSolverFF12, self).__init__()

        n_channels = obs_space.shape[0]
        im_size = obs_space.shape[1]

        init_relu = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0),
                                   nn.init.calculate_gain('relu'))

        self.encoder = nn.Sequential(
            init_relu(nn.Conv2d(n_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
        )

        self.recurse = nn.Sequential(
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),

        )

        self.out_layers = nn.Sequential(
            #             init_relu(nn.Conv2d(state_channels, 3, kernel_size=(3, 3), padding=1)),
            Flatten(),
            init_relu(nn.Linear(state_channels * im_size * im_size, 256)),
            nn.ReLU(),
            init_relu(nn.Linear(256, 1)),
        )

    def forward(self, obs, recurse_depth=5):
        h = self.encoder(obs)
        h = self.recurse(h)
        out = self.out_layers(h)
        outputs = torch.stack([out])

        return outputs


class SeqSolverFF5(nn.Module):
    def __init__(
            self,
            obs_space,
            state_channels=32,
    ):
        super(SeqSolverFF5, self).__init__()

        n_channels = obs_space.shape[0]
        im_size = obs_space.shape[1]

        init_relu = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0),
                                   nn.init.calculate_gain('relu'))

        self.encoder = nn.Sequential(
            init_relu(nn.Conv2d(n_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
        )

        self.recurse = nn.Sequential(
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
        )

        self.out_layers = nn.Sequential(
            #             init_relu(nn.Conv2d(state_channels, 3, kernel_size=(3, 3), padding=1)),
            Flatten(),
            init_relu(nn.Linear(state_channels * im_size * im_size, 256)),
            nn.ReLU(),
            init_relu(nn.Linear(256, 1)),
        )

    def forward(self, obs, recurse_depth=5):
        h = self.encoder(obs)
        h = self.recurse(h)
        out = self.out_layers(h)
        outputs = torch.stack([out])

        return outputs


class SeqSolverFF1(nn.Module):
    def __init__(
            self,
            obs_space,
            state_channels=32,
    ):
        super(SeqSolverFF1, self).__init__()

        n_channels = obs_space.shape[0]
        im_size = obs_space.shape[1]

        init_relu = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0),
                                   nn.init.calculate_gain('relu'))

        self.encoder = nn.Sequential(
            init_relu(nn.Conv2d(n_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
        )

        self.recurse = nn.Sequential(
            init_relu(nn.Conv2d(state_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
        )

        self.out_layers = nn.Sequential(
            #             init_relu(nn.Conv2d(state_channels, 3, kernel_size=(3, 3), padding=1)),
            #             nn.MaxPool2d(2),
            Flatten(),
            init_relu(nn.Linear(state_channels * im_size * im_size, 256)),
            nn.ReLU(),
            init_relu(nn.Linear(256, 1)),
        )

    def forward(self, obs, recurse_depth=5):
        h = self.encoder(obs)
        h = self.recurse(h)
        out = self.out_layers(h)
        outputs = torch.stack([out])

        return outputs


class SeqSolverCRNN(nn.Module):
    def __init__(
            self,
            obs_space,
            state_channels=32,
    ):
        super(SeqSolverCRNN, self).__init__()

        n_channels = obs_space.shape[0]
        im_size = obs_space.shape[1]

        init_relu = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0),
                                   nn.init.calculate_gain('relu'))

        self.encoder = nn.Sequential(
            init_relu(nn.Conv2d(n_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
        )

        self.recurse = ConvLSTMCell(state_channels, state_channels, kernel_size=(3, 3), bias=True)

        self.out_layers = nn.Sequential(
            #             init_relu(nn.Conv2d(state_channels, 3, kernel_size=(3, 3), padding=1)),
            Flatten(),
            init_relu(nn.Linear(state_channels * im_size * im_size, 256)),
            nn.ReLU(),
            init_relu(nn.Linear(256, 1)),
        )

    def forward(self, obs, recurse_depth=5):
        h = self.encoder(obs)

        outputs = []
        rnn_out = None
        for i in range(recurse_depth):
            rnn_out = self.recurse(h, rnn_out)
            h_cur, c_cur = rnn_out
            out = self.out_layers(h_cur)
            outputs.append(out)

        outputs = torch.stack(outputs)
        return outputs


class SeqSolverMuZero(nn.Module):
    def __init__(
            self,
            obs_space,
            state_channels=32,
    ):
        super(SeqSolverMuZero, self).__init__()

        n_channels = obs_space.shape[0]
        im_size = obs_space.shape[1]

        init_relu = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0),
                                   nn.init.calculate_gain('relu'))

        self.encoder = nn.Sequential(
            init_relu(nn.Conv2d(n_channels, state_channels, kernel_size=(3, 3), padding=1)),
            nn.ReLU(),
        )

        self.recurse = DynamicsNetwork(obs_space)

        self.out_layers = nn.Sequential(
            #             init_relu(nn.Conv2d(state_channels, 3, kernel_size=(3, 3), padding=1)),
            Flatten(),
            init_relu(nn.Linear(state_channels * im_size * im_size, 256)),
            nn.ReLU(),
            init_relu(nn.Linear(256, 1)),
        )

    def forward(self, obs, recurse_depth=5):
        h = self.encoder(obs)
        h = self.recurse(h)
        out = self.out_layers(h)
        outputs = torch.stack([out])

        return outputs

