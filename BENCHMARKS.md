# CogniOS Resource-Usage Observations

This document records observed CogniOS resource usage from individual runs on
October 2, 2026. These are observations, not a controlled benchmark.

## CogniOS daemon running

During one run, systemd reported:

| Measurement | Value |
|---|---:|
| Service state | Active (running) |
| Elapsed time at capture | About 3 minutes |
| Main process | `python .../cognios_as_daemon.py` |
| Service CPU time | 18.025 seconds |
| Service memory | 273.5 MB |
| Service memory peak | 280.6 MB |
| Process CPU in `top` at that instant | About 0.2% |

The CPU-time figure is accumulated since service start; it is not the current
CPU percentage. The `top` percentage is an instantaneous sample.

## CogniOS daemon stopped

After another run, `cognios.service` was **inactive (dead)**. It had stopped at
22:39:07 after a recorded run of about 54 minutes:

| Measurement | Value |
|---|---:|
| Service state at capture | Inactive (dead) |
| Recorded service duration | 54 minutes, 5 seconds |
| Recorded service CPU time | 4 minutes, 198 milliseconds |
| Recorded service memory peak | 424 MB |
| Recorded service swap peak | 132.9 MB |
| System CPU idle in `top` | About 98.6–98.8% |
| System memory total in `top` | About 11.7 GiB |

The CPU, memory-peak, and swap figures shown by `systemctl status` are retained
statistics for the service's **previous run**. They do not mean the stopped
service is still consuming those resources. The `top` output is a system-wide
snapshot, and there is no CogniOS daemon process listed in it.

## What can be concluded

- While running, the earlier sample showed about 274 MB of service memory and
  low instantaneous CPU use at the captured moment.
- Over the later, longer run, systemd recorded about 4 minutes of CPU time and
  a 424 MB memory peak.
- The stopped-service system readings are not a controlled “CogniOS off”
  baseline. The `top` CPU and memory readings describe the whole system, not
  the daemon's contribution.
- These runs have different durations and system workloads, so the values
  should not be treated as a precise before/after overhead comparison.

## How to collect a comparable measurement

Use the same workload and observation duration for both runs. Record
`systemctl --user status cognios.service` and `top` once while the daemon is
running, then stop the service with `cognios stop` and repeat the system-wide
`top` snapshot without the daemon. For cumulative daemon usage, compare
systemd's CPU time and memory peak after each equivalent run.
